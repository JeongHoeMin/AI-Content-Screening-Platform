from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import structlog

from app.config import (
    load_database_config,
    load_optional_telegram_config,
)
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
    create_workflow_execution_audit_persistence,
)
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
    manager = DashboardRunManager(
        filter_persistence=create_collection_filter_persistence(database_config),
        execution_audit_persistence=create_workflow_execution_audit_persistence(
            database_config
        ),
        schedule_persistence=persistence,
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


def main() -> None:
    """Run the long-lived Docker worker without shell cron state."""
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
