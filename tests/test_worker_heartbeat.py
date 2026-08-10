from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.harness.worker_heartbeat import (
    HeartbeatUnavailableError,
    WorkerHeartbeat,
    heartbeat_is_fresh,
    read_heartbeat,
    write_heartbeat,
)

_NOW: datetime = datetime(2026, 8, 10, 5, 0, tzinfo=timezone.utc)


def test_written_heartbeat_round_trips_as_an_aware_utc_time(tmp_path: Path) -> None:
    path = tmp_path / "beat"

    write_heartbeat(path, _NOW)

    assert read_heartbeat(path) == _NOW


def test_heartbeat_records_only_a_timestamp(tmp_path: Path) -> None:
    """The heartbeat is read by a healthcheck, so it must carry no run detail."""
    path = tmp_path / "beat"

    write_heartbeat(path, _NOW)

    assert path.read_text(encoding="utf-8") == _NOW.isoformat()


def test_reading_a_missing_empty_or_malformed_heartbeat_is_reported(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    empty = tmp_path / "empty"
    empty.write_text("", encoding="utf-8")
    malformed = tmp_path / "malformed"
    malformed.write_text("not-a-timestamp", encoding="utf-8")
    naive = tmp_path / "naive"
    naive.write_text("2026-08-10T05:00:00", encoding="utf-8")

    for path in (missing, empty, malformed, naive):
        with pytest.raises(HeartbeatUnavailableError):
            read_heartbeat(path)


def test_a_recent_heartbeat_is_fresh_and_an_old_one_is_not() -> None:
    assert heartbeat_is_fresh(_NOW, _NOW + timedelta(seconds=30), 90.0)
    assert heartbeat_is_fresh(_NOW, _NOW + timedelta(seconds=90), 90.0)
    assert not heartbeat_is_fresh(_NOW, _NOW + timedelta(seconds=91), 90.0)


def test_a_future_heartbeat_is_rejected_rather_than_treated_as_fresh() -> None:
    """Disagreeing clocks make the age meaningless, so it must not pass."""
    assert not heartbeat_is_fresh(_NOW, _NOW - timedelta(seconds=5), 90.0)


def test_freshness_compares_instants_across_differing_timezones() -> None:
    kst_same_instant = _NOW.astimezone(timezone(timedelta(hours=9)))

    assert heartbeat_is_fresh(kst_same_instant, _NOW + timedelta(seconds=10), 90.0)


def test_touch_survives_an_unwritable_heartbeat_path(tmp_path: Path) -> None:
    """A heartbeat write failure must never take down the worker loop."""
    unwritable = tmp_path / "file" / "beat"
    unwritable.parent.write_text("this is a file, not a directory", encoding="utf-8")

    WorkerHeartbeat(unwritable).touch(_NOW)

    assert not unwritable.exists()


def test_run_forever_keeps_refreshing_while_the_loop_is_responsive(tmp_path: Path) -> None:
    path = tmp_path / "beat"

    async def scenario() -> tuple[datetime, datetime]:
        heartbeat = WorkerHeartbeat(path, interval_seconds=0.01)
        task = asyncio.create_task(heartbeat.run_forever())
        await asyncio.sleep(0.05)
        first = read_heartbeat(path)
        await asyncio.sleep(0.05)
        second = read_heartbeat(path)
        task.cancel()
        return first, second

    first, second = asyncio.run(scenario())

    assert second >= first
