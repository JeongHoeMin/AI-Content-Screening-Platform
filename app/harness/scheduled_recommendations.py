from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol, Tuple, runtime_checkable

import structlog
from pydantic import BaseModel, ConfigDict, Field

from app.harness.telegram import TelegramRecommendationSummary, TelegramReporter
from app.models.scheduled_recommendation import ScheduledRecommendationJob
from app.persistence.schedule_repository import ClaimedScheduledRecommendationJob

logger = structlog.get_logger(__name__)


class ScheduledRecommendationOutcome(BaseModel):
    """Safe terminal output from one scheduled recommendation execution."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(min_length=1, max_length=64)
    recommendation_count: int = Field(ge=0)
    recommendations: Tuple[str, ...] = Field(default=(), max_length=10)


@runtime_checkable
class ScheduledRecommendationRunner(Protocol):
    """Harness-owned business execution invoked after a durable lease claim."""

    async def run(
        self,
        job: ScheduledRecommendationJob,
        scheduled_for: datetime,
    ) -> ScheduledRecommendationOutcome:
        """Execute one configured RSS recommendation run."""


class DueSchedulePersistence(Protocol):
    """Small worker boundary for atomically claiming a due schedule."""

    async def claim_due(
        self,
        now_utc: datetime,
        lease_owner: str,
        lease_until: datetime,
    ) -> Optional[ClaimedScheduledRecommendationJob]:
        """Lease at most one due run slot."""

    async def complete_execution(
        self,
        execution_id: str,
        job_id: str,
        lease_owner: str,
        status: str,
        error_type: Optional[str],
        finished_at: datetime,
    ) -> bool:
        """Persist one terminal execution observation."""

    async def renew_lease(
        self,
        job_id: str,
        execution_id: str,
        lease_owner: str,
        lease_until: datetime,
    ) -> bool:
        """Renew a live schedule worker lease."""


class ScheduledRecommendationWorker:
    """Poll due KST schedules without mutating state outside the Harness adapter."""

    def __init__(
        self,
        persistence: DueSchedulePersistence,
        runner: ScheduledRecommendationRunner,
        reporter: Optional[TelegramReporter],
        worker_id: str,
    ) -> None:
        self._persistence: DueSchedulePersistence = persistence
        self._runner: ScheduledRecommendationRunner = runner
        self._reporter: Optional[TelegramReporter] = reporter
        self._worker_id: str = worker_id

    async def run_due(self, now_utc: datetime) -> int:
        """Claim and run every currently due job, returning the completed count."""
        completed_count: int = 0
        while True:
            claim: Optional[ClaimedScheduledRecommendationJob] = (
                await self._persistence.claim_due(
                    now_utc=now_utc,
                    lease_owner=self._worker_id,
                    lease_until=now_utc + timedelta(minutes=30),
                )
            )
            if claim is None:
                return completed_count
            completed_count += 1
            await self._run_claim(claim)

    async def _run_claim(self, claim: ClaimedScheduledRecommendationJob) -> None:
        heartbeat_task: asyncio.Task[None] = asyncio.create_task(
            self._renew_lease_until_finished(claim)
        )
        try:
            outcome: ScheduledRecommendationOutcome = await self._runner.run(
                claim.job,
                claim.scheduled_for,
            )
        except Exception as error:
            logger.error(
                "scheduled_recommendation_failed",
                job_id=claim.job.id,
                error_type=type(error).__name__,
            )
            await self._persistence.complete_execution(
                execution_id=claim.execution_id,
                job_id=claim.job.id,
                lease_owner=claim.lease_owner,
                status="failed",
                error_type=type(error).__name__,
                finished_at=datetime.now(claim.scheduled_for.tzinfo),
            )
            return
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        completed: bool = await self._persistence.complete_execution(
            execution_id=claim.execution_id,
            job_id=claim.job.id,
            lease_owner=claim.lease_owner,
            status="completed",
            error_type=None,
            finished_at=datetime.now(claim.scheduled_for.tzinfo),
        )
        if not completed:
            logger.warning(
                "scheduled_recommendation_terminal_status_not_recorded",
                job_id=claim.job.id,
            )
            return
        if not claim.job.telegram_enabled or self._reporter is None:
            return
        delivery_error: Optional[str] = await self._reporter.deliver(
            TelegramRecommendationSummary(
                execution_id=outcome.execution_id,
                scheduled_for=claim.scheduled_for,
                recommendation_count=outcome.recommendation_count,
                recommendations=outcome.recommendations,
            )
        )
        if delivery_error is not None:
            logger.warning(
                "scheduled_recommendation_telegram_delivery_failed",
                job_id=claim.job.id,
                error_type=delivery_error,
            )

    async def _renew_lease_until_finished(
        self,
        claim: ClaimedScheduledRecommendationJob,
    ) -> None:
        """Keep a live workflow's lease ahead of the 30-minute expiry window."""
        while True:
            await asyncio.sleep(300)
            renewed: bool = await self._persistence.renew_lease(
                job_id=claim.job.id,
                execution_id=claim.execution_id,
                lease_owner=claim.lease_owner,
                lease_until=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            if renewed:
                continue
            logger.warning(
                "scheduled_recommendation_lease_not_renewed",
                job_id=claim.job.id,
            )
            return
