"""Container healthcheck entry point for the scheduled recommendation worker.

The worker serves no HTTP, so liveness is judged from the heartbeat it refreshes
on its own interval rather than from a request to a port it never opens.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.harness.worker_heartbeat import (
    DEFAULT_HEARTBEAT_PATH,
    DEFAULT_MAX_AGE_SECONDS,
    HeartbeatUnavailableError,
    heartbeat_is_fresh,
    read_heartbeat,
)


def main() -> int:
    """Exit 0 only while the worker's heartbeat is present and recent."""
    path = Path(os.environ.get("SCHEDULE_WORKER_HEARTBEAT_PATH", DEFAULT_HEARTBEAT_PATH))
    raw_max_age: str = os.environ.get("SCHEDULE_WORKER_HEARTBEAT_MAX_AGE_SECONDS", "").strip()
    try:
        max_age_seconds: float = float(raw_max_age) if raw_max_age else DEFAULT_MAX_AGE_SECONDS
    except ValueError:
        print("SCHEDULE_WORKER_HEARTBEAT_MAX_AGE_SECONDS must be a number", file=sys.stderr)
        return 1
    try:
        recorded: datetime = read_heartbeat(path)
    except HeartbeatUnavailableError as error:
        print(str(error), file=sys.stderr)
        return 1
    if not heartbeat_is_fresh(recorded, datetime.now(timezone.utc), max_age_seconds):
        print("Worker heartbeat is stale", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
