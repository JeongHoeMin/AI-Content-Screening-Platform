from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.harness.scheduler import DailySchedule, DailyWorkflowScheduler


def utc_datetime(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 7, 30, hour, minute, second, tzinfo=timezone.utc)


def test_daily_schedule_returns_next_utc_slot_strictly_after_current_time() -> None:
    schedule: DailySchedule = DailySchedule(hour=9, minute=30)

    assert schedule.next_run_at(utc_datetime(8, 0)) == utc_datetime(9, 30)
    assert schedule.next_run_at(utc_datetime(9, 30)) == datetime(
        2026, 7, 31, 9, 30, tzinfo=timezone.utc
    )


def test_daily_schedule_rejects_naive_or_non_utc_time() -> None:
    schedule: DailySchedule = DailySchedule(hour=0, minute=0)

    with pytest.raises(ValueError, match="UTC"):
        schedule.next_run_at(datetime(2026, 7, 30, 0, 0))


@pytest.mark.anyio
async def test_scheduler_runs_one_due_job_and_advances_to_tomorrow() -> None:
    calls: list[str] = []

    async def job() -> None:
        calls.append("run")

    scheduler: DailyWorkflowScheduler = DailyWorkflowScheduler(
        DailySchedule(hour=9, minute=30), job, clock=lambda: utc_datetime(8, 0)
    )

    assert await scheduler.run_pending(utc_datetime(9, 29)) is False
    assert await scheduler.run_pending(utc_datetime(9, 30)) is True
    assert calls == ["run"]
    assert scheduler.next_run_at == datetime(2026, 7, 31, 9, 30, tzinfo=timezone.utc)


@pytest.mark.anyio
async def test_scheduler_failure_does_not_repeat_same_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    log_events: list[dict[str, object]] = []

    async def job() -> None:
        calls.append("run")
        raise RuntimeError("sensitive content")

    class Logger:
        def error(self, event: str, **kwargs: object) -> None:
            log_events.append({"event": event, **kwargs})

    monkeypatch.setattr("app.harness.scheduler.logger", Logger())
    scheduler: DailyWorkflowScheduler = DailyWorkflowScheduler(
        DailySchedule(hour=9, minute=30), job, clock=lambda: utc_datetime(8, 0)
    )

    assert await scheduler.run_pending(utc_datetime(9, 30)) is True
    assert await scheduler.run_pending(utc_datetime(9, 30)) is False
    assert calls == ["run"]
    assert log_events == [
        {
            "event": "scheduled_workflow_failed",
            "error_type": "RuntimeError",
            "scheduled_for": "2026-07-30T09:30:00+00:00",
        }
    ]


@pytest.mark.anyio
async def test_scheduler_serve_stops_without_running_when_already_cancelled() -> None:
    calls: list[str] = []

    async def job() -> None:
        calls.append("run")

    stop_event: asyncio.Event = asyncio.Event()
    stop_event.set()
    scheduler: DailyWorkflowScheduler = DailyWorkflowScheduler(
        DailySchedule(hour=9, minute=30), job, clock=lambda: utc_datetime(8, 0)
    )

    await scheduler.serve(stop_event)

    assert calls == []
