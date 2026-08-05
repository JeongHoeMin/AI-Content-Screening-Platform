from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.web.app import DashboardRunManager


class _Recorder:
    def __init__(self, fail: bool = False) -> None:
        self.fail: bool = fail
        self.calls: list[tuple[str, tuple[object, ...], datetime]] = []

    async def record_entries(
        self,
        run_id: str,
        recommendations: tuple[object, ...],
        observed_at: datetime,
    ) -> None:
        self.calls.append((run_id, recommendations, observed_at))
        if self.fail:
            raise RuntimeError("price persistence failed")


def test_dashboard_price_recording_is_optional_and_best_effort() -> None:
    manager = DashboardRunManager()

    asyncio.run(manager._record_price_entries("run-1", (), datetime(2026, 8, 5, tzinfo=timezone.utc)))

    assert manager._price_recorder is None


def test_dashboard_price_recording_does_not_raise_when_recorder_fails() -> None:
    recorder = _Recorder(fail=True)
    manager = DashboardRunManager(price_recorder=recorder)  # type: ignore[arg-type]

    asyncio.run(manager._record_price_entries("run-1", (), datetime(2026, 8, 5, tzinfo=timezone.utc)))

    assert len(recorder.calls) == 1
