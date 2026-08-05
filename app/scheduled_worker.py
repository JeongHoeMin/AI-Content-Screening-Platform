from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import (
    load_krx_config,
    load_database_config,
    load_optional_kis_config,
    load_optional_telegram_config,
)
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
from app.harness.recommendation_prices import RecommendationPriceRecorder
from app.market_prices import KisRealtimePriceClient, KrxClosingPriceClient, MarketPriceService
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
        recommendations: tuple[str, ...] = tuple(
            f"{item.company_name} · {item.action}" for item in result.recommendations[:10]
        )
        return ScheduledRecommendationOutcome(
            execution_id=result.run_id,
            recommendation_count=len(result.recommendations),
            recommendations=recommendations,
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
    while True:
        completed: int = await worker.run_due(datetime.now(timezone.utc))
        if completed:
            logger.info("scheduled_recommendation_runs_completed", count=completed)
        await asyncio.sleep(30)


def _create_optional_price_recorder(
    database_config: DatabaseConfig,
) -> Optional[RecommendationPriceRecorder]:
    """Keep a schedule worker available when price lookup configuration is absent."""
    try:
        price_service: MarketPriceService = MarketPriceService(
            KisRealtimePriceClient(load_optional_kis_config()),
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


def main() -> None:
    """Run the long-lived Docker worker without shell cron state."""
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
