from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol

from sqlalchemy import and_, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduled_recommendation import ScheduledRecommendationJob
from app.persistence.schema import (
    scheduled_recommendation_executions,
    scheduled_recommendation_jobs,
)


@dataclass(frozen=True)
class ClaimedScheduledRecommendationJob:
    """One due job leased by a worker for exactly one persisted slot."""

    job: ScheduledRecommendationJob
    scheduled_for: datetime
    lease_owner: str
    lease_until: datetime
    execution_id: str


class ScheduleVersionConflictError(RuntimeError):
    """Raised when a dashboard save targets an obsolete schedule version."""


class ScheduledRecommendationRepository(Protocol):
    """Harness-owned storage contract for KST schedule configuration and leases."""

    async def get(self, job_id: str) -> Optional[ScheduledRecommendationJob]:
        """Load the current schedule configuration, when present."""

    async def save(
        self,
        job: ScheduledRecommendationJob,
        next_run_at: datetime,
        expected_version: Optional[int],
    ) -> None:
        """Create or replace the single versioned configuration."""

    async def claim_due(
        self,
        now_utc: datetime,
        lease_owner: str,
        lease_until: datetime,
    ) -> Optional[ClaimedScheduledRecommendationJob]:
        """Lease at most one due job while moving its next run forward."""

    async def complete_execution(
        self,
        execution_id: str,
        status: str,
        error_type: Optional[str],
        finished_at: datetime,
    ) -> bool:
        """Persist a bounded terminal observation for one claimed schedule slot."""


class SqlAlchemyScheduledRecommendationRepository:
    """PostgreSQL lease adapter used only by the scheduled execution Harness."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def get(self, job_id: str) -> Optional[ScheduledRecommendationJob]:
        row = (
            await self._session.execute(
                select(scheduled_recommendation_jobs).where(
                    scheduled_recommendation_jobs.c.id == job_id
                )
            )
        ).mappings().first()
        if row is None:
            return None
        return self._job_from_row(row)

    async def save(
        self,
        job: ScheduledRecommendationJob,
        next_run_at: datetime,
        expected_version: Optional[int],
    ) -> None:
        values: dict[str, object] = self._job_values(job, next_run_at)
        if expected_version is None:
            inserted_id: Optional[str] = (
                await self._session.execute(
                    postgresql_insert(scheduled_recommendation_jobs)
                    .values(**values)
                    .on_conflict_do_nothing(index_elements=["id"])
                    .returning(scheduled_recommendation_jobs.c.id)
                )
            ).scalar_one_or_none()
            if inserted_id is None:
                raise ScheduleVersionConflictError("Schedule was created elsewhere")
            return
        result = await self._session.execute(
            update(scheduled_recommendation_jobs)
            .where(
                and_(
                    scheduled_recommendation_jobs.c.id == job.id,
                    scheduled_recommendation_jobs.c.version == expected_version,
                )
            )
            .values(**values)
        )
        if result.rowcount != 1:
            raise ScheduleVersionConflictError("Schedule version is stale")

    async def claim_due(
        self,
        now_utc: datetime,
        lease_owner: str,
        lease_until: datetime,
    ) -> Optional[ClaimedScheduledRecommendationJob]:
        query = (
            select(scheduled_recommendation_jobs)
            .where(
                and_(
                    scheduled_recommendation_jobs.c.active == 1,
                    scheduled_recommendation_jobs.c.next_run_at <= now_utc,
                    or_(
                        scheduled_recommendation_jobs.c.lease_until.is_(None),
                        scheduled_recommendation_jobs.c.lease_until < now_utc,
                    ),
                )
            )
            .order_by(scheduled_recommendation_jobs.c.next_run_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        row = (await self._session.execute(query)).mappings().first()
        if row is None:
            return None
        job: ScheduledRecommendationJob = self._job_from_row(row)
        scheduled_for: datetime = row["next_run_at"]
        next_run_at: datetime = job.next_run_at(scheduled_for)
        execution_id: str = f"scheduled-{job.id}-{scheduled_for.timestamp():.0f}"
        existing_execution_id: Optional[str] = (
            await self._session.execute(
                select(scheduled_recommendation_executions.c.id).where(
                    and_(
                        scheduled_recommendation_executions.c.job_id == job.id,
                        scheduled_recommendation_executions.c.scheduled_for == scheduled_for,
                    )
                )
            )
        ).scalar_one_or_none()
        if existing_execution_id is not None:
            await self._session.execute(
                update(scheduled_recommendation_jobs)
                .where(scheduled_recommendation_jobs.c.id == job.id)
                .values(
                    next_run_at=next_run_at,
                    last_run_at=scheduled_for,
                    lease_owner=None,
                    lease_until=None,
                )
            )
            await self._session.execute(
                update(scheduled_recommendation_executions)
                .where(
                    and_(
                        scheduled_recommendation_executions.c.id == existing_execution_id,
                        scheduled_recommendation_executions.c.status == "running",
                    )
                )
                .values(
                    status="abandoned",
                    error_type="lease_expired",
                    finished_at=now_utc,
                )
            )
            return None
        await self._session.execute(
            insert(scheduled_recommendation_executions).values(
                id=execution_id,
                job_id=job.id,
                scheduled_for=scheduled_for,
                started_at=now_utc,
                status="running",
            )
        )
        await self._session.execute(
            update(scheduled_recommendation_jobs)
            .where(scheduled_recommendation_jobs.c.id == job.id)
            .values(
                next_run_at=next_run_at,
                last_run_at=scheduled_for,
                lease_owner=lease_owner,
                lease_until=lease_until,
            )
        )
        return ClaimedScheduledRecommendationJob(
            job=job,
            scheduled_for=scheduled_for,
            lease_owner=lease_owner,
            lease_until=lease_until,
            execution_id=execution_id,
        )

    async def complete_execution(
        self,
        execution_id: str,
        job_id: str,
        lease_owner: str,
        status: str,
        error_type: Optional[str],
        finished_at: datetime,
    ) -> bool:
        current_lease_owner: Optional[str] = (
            await self._session.execute(
                select(scheduled_recommendation_jobs.c.lease_owner)
                .where(scheduled_recommendation_jobs.c.id == job_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if current_lease_owner != lease_owner:
            return False
        result = await self._session.execute(
            update(scheduled_recommendation_executions)
            .where(
                and_(
                    scheduled_recommendation_executions.c.id == execution_id,
                    scheduled_recommendation_executions.c.status == "running",
                )
            )
            .values(
                status=status,
                error_type=error_type,
                finished_at=finished_at,
            )
        )
        if result.rowcount != 1:
            return False
        await self._session.execute(
            update(scheduled_recommendation_jobs)
            .where(
                and_(
                    scheduled_recommendation_jobs.c.id == job_id,
                    scheduled_recommendation_jobs.c.lease_owner == lease_owner,
                )
            )
            .values(lease_owner=None, lease_until=None)
        )
        return True

    async def renew_lease(
        self,
        job_id: str,
        execution_id: str,
        lease_owner: str,
        lease_until: datetime,
    ) -> bool:
        active_execution_id: Optional[str] = (
            await self._session.execute(
                select(scheduled_recommendation_executions.c.id).where(
                    and_(
                        scheduled_recommendation_executions.c.id == execution_id,
                        scheduled_recommendation_executions.c.job_id == job_id,
                        scheduled_recommendation_executions.c.status == "running",
                    )
                )
            )
        ).scalar_one_or_none()
        if active_execution_id is None:
            return False
        result = await self._session.execute(
            update(scheduled_recommendation_jobs)
            .where(
                and_(
                    scheduled_recommendation_jobs.c.id == job_id,
                    scheduled_recommendation_jobs.c.lease_owner == lease_owner,
                )
            )
            .values(lease_until=lease_until)
        )
        return result.rowcount == 1

    @staticmethod
    def _job_from_row(row: object) -> ScheduledRecommendationJob:
        values = row
        return ScheduledRecommendationJob(
            id=str(values["id"]),
            active=bool(values["active"]),
            cron_expression=str(values["cron_expression"]),
            timezone=str(values["timezone"]),
            themes=tuple(values["themes"]),
            topics=tuple(values["topics"]),
            limit=int(values["limit"]),
            telegram_enabled=bool(values["telegram_enabled"]),
            version=int(values["version"]),
        )

    @staticmethod
    def _job_values(
        job: ScheduledRecommendationJob,
        next_run_at: datetime,
    ) -> dict[str, object]:
        return {
            "id": job.id,
            "active": int(job.active),
            "cron_expression": job.cron_expression,
            "timezone": job.timezone,
            "themes": [item.value for item in job.themes],
            "topics": [item.value for item in job.topics],
            "limit": job.limit,
            "telegram_enabled": int(job.telegram_enabled),
            "version": job.version,
            "next_run_at": next_run_at,
        }
