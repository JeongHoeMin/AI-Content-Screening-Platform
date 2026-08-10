from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import structlog

from app.config import (
    KisConfig,
    load_krx_config,
    load_database_config,
    load_optional_kis_config,
    load_optional_telegram_config,
)
from app.config.errors import ConfigurationError
from app.config.persistence import DatabaseConfig
from app.harness.scheduled_recommendations import (
    ScheduledRecommendationOutcome,
    ScheduledRecommendationRunner,
    ScheduledRecommendationWorker,
)
from app.harness.telegram import TelegramBotReporter, TelegramReporter
from app.models.scheduled_recommendation import ScheduledRecommendationJob
from app.persistence import (
    create_collection_filter_persistence,
    create_scheduled_recommendation_persistence,
    create_recommendation_price_persistence,
    create_workflow_execution_audit_persistence,
)
from app.harness.entry_price_backfill import (
    DailyEntryPriceBackfill,
    HistoricalClosingPriceCapture,
    RecommendationEntryPriceBackfill,
)
from app.harness.recommendation_prices import (
    RecommendationPerformanceService,
    RecommendationPriceRecorder,
)
from app.harness.recommendation_summary import (
    RecommendationSummaryInput,
    build_recommendation_lines,
)
from app.harness.worker_heartbeat import DEFAULT_HEARTBEAT_PATH, WorkerHeartbeat
from app.market_prices import KisRealtimePriceClient, KrxClosingPriceClient, MarketPriceService
from app.market_prices.performance import RecommendationPerformanceResponse
from app.web.app import DashboardRunManager, RecommendationRunRequest

logger = structlog.get_logger(__name__)


class DashboardScheduledRecommendationRunner:
    """Adapter that reuses the dashboard's verified RSS workflow for cron runs."""

    def __init__(self, manager: DashboardRunManager) -> None:
        self._manager: DashboardRunManager = manager

    async def run(
        self,
        job: ScheduledRecommendationJob,
        scheduled_for: datetime,
    ) -> ScheduledRecommendationOutcome:
        result = await self._manager.run_scheduled(
            RecommendationRunRequest(
                limit=job.limit,
                themes=job.themes,
                topics=job.topics,
            )
        )
        performance: RecommendationPerformanceResponse = (
            await self._manager.recommendation_performance()
        )
        return ScheduledRecommendationOutcome(
            execution_id=result.run_id,
            recommendation_count=len(result.recommendations),
            recommendations=build_recommendation_lines(
                [
                    RecommendationSummaryInput(
                        recommendation_index=recommendation.recommendation_index,
                        company_name=recommendation.company_name,
                        action=recommendation.action,
                    )
                    for recommendation in result.recommendations
                ],
                [item for item in performance.items if item.run_id == result.run_id],
            ),
        )


async def run_forever() -> None:
    """Poll durable schedules; all displayed schedule times are Asia/Seoul based."""
    database_config = load_database_config()
    persistence = create_scheduled_recommendation_persistence(database_config)
    price_recorder: Optional[RecommendationPriceRecorder] = _create_optional_price_recorder(
        database_config
    )
    manager = DashboardRunManager(
        filter_persistence=create_collection_filter_persistence(database_config),
        execution_audit_persistence=create_workflow_execution_audit_persistence(
            database_config
        ),
        schedule_persistence=persistence,
        price_recorder=price_recorder,
        performance_service=_create_optional_performance_service(database_config),
    )
    telegram_config = load_optional_telegram_config()
    reporter: Optional[TelegramReporter] = (
        TelegramBotReporter(telegram_config) if telegram_config is not None else None
    )
    worker_id: str = os.environ.get("SCHEDULE_WORKER_ID", "schedule-worker").strip()
    worker = ScheduledRecommendationWorker(
        persistence=persistence,
        runner=DashboardScheduledRecommendationRunner(manager),
        reporter=reporter,
        worker_id=worker_id or "schedule-worker",
    )
    # Refreshed on its own interval so a legitimately long run is not mistaken
    # for a stalled worker, while a dead process or blocked loop stops it.
    heartbeat = WorkerHeartbeat(
        Path(os.environ.get("SCHEDULE_WORKER_HEARTBEAT_PATH", DEFAULT_HEARTBEAT_PATH))
    )
    heartbeat.touch()
    heartbeat_task: asyncio.Task[None] = asyncio.create_task(heartbeat.run_forever())
    # A recommendation whose entry lookup failed keeps no price at all, so this
    # retries those once a day against the closing-price source instead of
    # leaving the return permanently unknown.
    daily_backfill: Optional[DailyEntryPriceBackfill] = _create_optional_daily_backfill(
        database_config
    )
    try:
        while True:
            now_utc: datetime = datetime.now(timezone.utc)
            completed: int = await worker.run_due(now_utc)
            if completed:
                logger.info("scheduled_recommendation_runs_completed", count=completed)
            if daily_backfill is not None:
                await daily_backfill.run_if_due(now_utc)
            await asyncio.sleep(30)
    finally:
        heartbeat_task.cancel()


def _create_optional_daily_backfill(
    database_config: DatabaseConfig,
) -> Optional[DailyEntryPriceBackfill]:
    """Keep the worker running when the closing-price source is not configured."""
    try:
        return DailyEntryPriceBackfill(
            RecommendationEntryPriceBackfill(
                HistoricalClosingPriceCapture(KrxClosingPriceClient(load_krx_config())),
                create_recommendation_price_persistence(database_config),
            )
        )
    except Exception as error:
        logger.warning(
            "scheduled_recommendation_entry_backfill_unavailable",
            error_type=type(error).__name__,
        )
        return None


def _create_optional_price_recorder(
    database_config: DatabaseConfig,
) -> Optional[RecommendationPriceRecorder]:
    """Keep a schedule worker available when price lookup configuration is absent."""
    try:
        try:
            kis_config: Optional[KisConfig] = load_optional_kis_config()
        except ConfigurationError:
            logger.warning(
                "scheduled_recommendation_price_kis_unavailable",
                reason="partial_configuration",
            )
            kis_config = None
        price_service: MarketPriceService = MarketPriceService(
            KisRealtimePriceClient(kis_config),
            KrxClosingPriceClient(load_krx_config()),
        )
        return RecommendationPriceRecorder(
            price_service,
            create_recommendation_price_persistence(database_config),
        )
    except Exception as error:
        logger.warning(
            "scheduled_recommendation_price_recorder_unavailable",
            error_type=type(error).__name__,
        )
        return None


def _create_optional_performance_service(
    database_config: DatabaseConfig,
) -> Optional[RecommendationPerformanceService]:
    """Keep scheduled price summaries available without affecting the main run result."""
    try:
        try:
            kis_config: Optional[KisConfig] = load_optional_kis_config()
        except ConfigurationError:
            logger.warning(
                "scheduled_recommendation_performance_kis_unavailable",
                reason="partial_configuration",
            )
            kis_config = None
        price_service: MarketPriceService = MarketPriceService(
            KisRealtimePriceClient(kis_config),
            KrxClosingPriceClient(load_krx_config()),
        )
        return RecommendationPerformanceService(
            price_service,
            create_recommendation_price_persistence(database_config),
        )
    except Exception as error:
        logger.warning(
            "scheduled_recommendation_performance_unavailable",
            error_type=type(error).__name__,
        )
        return None


def main() -> None:
    """Run the long-lived Docker worker without shell cron state."""
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
