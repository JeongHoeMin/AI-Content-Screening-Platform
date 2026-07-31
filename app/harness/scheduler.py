from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)

Clock = Callable[[], datetime]
ScheduledJob = Callable[[], Awaitable[None]]


class DailySchedule(BaseModel):
    """One daily UTC execution time without local-time or DST ambiguity."""

    model_config = ConfigDict(frozen=True)

    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)

    def next_run_at(self, after: datetime) -> datetime:
        """Return the first schedule time strictly after the supplied UTC instant."""
        if after.tzinfo is None or after.utcoffset() != timedelta(0):
            raise ValueError("DailySchedule requires an aware UTC datetime")
        target: datetime = after.replace(
            hour=self.hour,
            minute=self.minute,
            second=0,
            microsecond=0,
            tzinfo=timezone.utc,
        )
        if target <= after:
            target += timedelta(days=1)
        return target


class DailyWorkflowScheduler:
    """Run a supplied Harness-owned job daily while isolating individual failures."""

    def __init__(
        self,
        schedule: DailySchedule,
        job: ScheduledJob,
        clock: Clock = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._schedule: DailySchedule = schedule
        self._job: ScheduledJob = job
        self._clock: Clock = clock
        self._next_run_at: datetime = schedule.next_run_at(clock())
        self._run_lock: asyncio.Lock = asyncio.Lock()

    @property
    def next_run_at(self) -> datetime:
        """Expose the immutable next planned execution time for operational status."""
        return self._next_run_at

    async def run_pending(self, now: Optional[datetime] = None) -> bool:
        """Run exactly one due job and advance the schedule even when the job fails."""
        current_time: datetime = now if now is not None else self._clock()
        async with self._run_lock:
            if current_time < self._next_run_at:
                return False
            scheduled_for: datetime = self._next_run_at
            self._next_run_at = self._schedule.next_run_at(current_time)
            try:
                await self._job()
            except Exception as error:
                logger.error(
                    "scheduled_workflow_failed",
                    error_type=type(error).__name__,
                    scheduled_for=scheduled_for.isoformat(),
                )
            return True

    async def serve(self, stop_event: asyncio.Event) -> None:
        """Wait for scheduled work until a caller requests graceful shutdown."""
        while not stop_event.is_set():
            now: datetime = self._clock()
            delay_seconds: float = max(
                0.0,
                (self._next_run_at - now).total_seconds(),
            )
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay_seconds)
            except asyncio.TimeoutError:
                await self.run_pending(self._clock())
