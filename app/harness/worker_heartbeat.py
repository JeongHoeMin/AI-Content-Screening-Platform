"""Liveness heartbeat for the long-lived scheduled recommendation worker."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_HEARTBEAT_PATH: str = "/tmp/schedule-worker.heartbeat"
DEFAULT_INTERVAL_SECONDS: float = 10.0
DEFAULT_MAX_AGE_SECONDS: float = 90.0


class HeartbeatUnavailableError(Exception):
    """The heartbeat could not be read or does not hold a usable timestamp."""


def write_heartbeat(path: Path, now: datetime) -> None:
    """Record only an observation time; the heartbeat carries no run detail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(now.astimezone(timezone.utc).isoformat(), encoding="utf-8")


def read_heartbeat(path: Path) -> datetime:
    """Read the last recorded observation time as an aware UTC datetime."""
    try:
        raw: str = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise HeartbeatUnavailableError("Heartbeat file could not be read") from error
    if not raw:
        raise HeartbeatUnavailableError("Heartbeat file is empty")
    try:
        recorded: datetime = datetime.fromisoformat(raw)
    except ValueError as error:
        raise HeartbeatUnavailableError("Heartbeat timestamp is malformed") from error
    if recorded.tzinfo is None:
        raise HeartbeatUnavailableError("Heartbeat timestamp is not timezone aware")
    return recorded.astimezone(timezone.utc)


def heartbeat_is_fresh(
    recorded: datetime,
    now: datetime,
    max_age_seconds: float = DEFAULT_MAX_AGE_SECONDS,
) -> bool:
    """Treat a heartbeat as live only inside the allowed age window.

    A timestamp from the future is rejected as well: it means the recorded and
    checking clocks disagree, so the age cannot be trusted either way.
    """
    age: timedelta = now.astimezone(timezone.utc) - recorded.astimezone(timezone.utc)
    if age < timedelta(0):
        return False
    return age <= timedelta(seconds=max_age_seconds)


class WorkerHeartbeat:
    """Refresh a heartbeat file independently of the work the loop is doing."""

    def __init__(
        self,
        path: Path,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self._path: Path = path
        self._interval_seconds: float = interval_seconds

    def touch(self, now: Optional[datetime] = None) -> None:
        """Record one observation without letting a write failure stop the worker."""
        try:
            write_heartbeat(self._path, now or datetime.now(timezone.utc))
        except OSError as error:
            logger.warning(
                "worker_heartbeat_write_failed",
                error_type=type(error).__name__,
            )

    async def run_forever(self) -> None:
        """Refresh on a fixed interval so a long run does not look like a stall."""
        while True:
            self.touch()
            await asyncio.sleep(self._interval_seconds)
