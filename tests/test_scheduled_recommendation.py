from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.scheduled_recommendation import ScheduledRecommendationJob


def test_schedule_rejects_non_kst_or_invalid_five_field_cron() -> None:
    with pytest.raises(ValidationError):
        ScheduledRecommendationJob(
            id="daily",
            cron_expression="invalid",
            timezone="Asia/Seoul",
        )

    with pytest.raises(ValidationError):
        ScheduledRecommendationJob(
            id="daily",
            cron_expression="0 8 * * *",
            timezone="UTC",
        )


def test_schedule_calculates_next_kst_slot_as_utc() -> None:
    job = ScheduledRecommendationJob(
        id="daily",
        cron_expression="0 8 * * *",
        timezone="Asia/Seoul",
    )

    assert job.next_run_at(datetime(2026, 8, 5, 22, 0, tzinfo=timezone.utc)) == datetime(
        2026,
        8,
        5,
        23,
        0,
        tzinfo=timezone.utc,
    )


def test_schedule_uses_standard_day_of_month_or_weekday_matching() -> None:
    job = ScheduledRecommendationJob(
        id="monthly-or-monday",
        cron_expression="0 8 1 * 1",
    )

    assert job.next_run_at(datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)) == datetime(
        2026,
        8,
        2,
        23,
        0,
        tzinfo=timezone.utc,
    )
