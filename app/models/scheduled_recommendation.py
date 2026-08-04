from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Tuple
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.collection_filter import InvestmentTheme, NewsTopic

_KST: ZoneInfo = ZoneInfo("Asia/Seoul")
_CRON_FIELD_LIMITS: tuple[tuple[int, int], ...] = (
    (0, 59),
    (0, 23),
    (1, 31),
    (1, 12),
    (0, 6),
)


def _parse_cron_field(value: str, minimum: int, maximum: int) -> frozenset[int]:
    """Parse a bounded five-field cron component without executing user input."""
    values: set[int] = set()
    for part in value.split(","):
        base, separator, step_text = part.partition("/")
        if separator and (not step_text.isdecimal() or int(step_text) <= 0):
            raise ValueError("Cron step must be a positive integer")
        step: int = int(step_text) if separator else 1
        if base == "*":
            start, end = minimum, maximum
        elif "-" in base:
            start_text, end_text = base.split("-", maxsplit=1)
            if not start_text.isdecimal() or not end_text.isdecimal():
                raise ValueError("Cron range must contain integers")
            start, end = int(start_text), int(end_text)
        elif base.isdecimal():
            start = end = int(base)
        else:
            raise ValueError("Cron field is invalid")
        if start < minimum or end > maximum or start > end:
            raise ValueError("Cron value is outside its allowed range")
        values.update(range(start, end + 1, step))
    return frozenset(values)


def _cron_fields(expression: str) -> tuple[frozenset[int], ...]:
    fields: tuple[str, ...] = tuple(expression.split())
    if len(fields) != 5:
        raise ValueError("Cron expression must have exactly five fields")
    return tuple(
        _parse_cron_field(field, minimum, maximum)
        for field, (minimum, maximum) in zip(fields, _CRON_FIELD_LIMITS)
    )


class ScheduledRecommendationJob(BaseModel):
    """Validated DB-safe configuration for one KST scheduled recommendation run."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=64)
    active: bool = True
    cron_expression: str = Field(min_length=9, max_length=128)
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    themes: Tuple[InvestmentTheme, ...] = ()
    topics: Tuple[NewsTopic, ...] = ()
    limit: Literal[25, 50, 100] = 25
    telegram_enabled: bool = False
    version: int = Field(default=1, ge=1)

    @field_validator("cron_expression")
    @classmethod
    def _validate_cron_expression(cls, value: str) -> str:
        _cron_fields(value)
        return value

    def next_run_at(self, after: datetime) -> datetime:
        """Return the next KST cron slot strictly after an aware UTC timestamp."""
        if after.tzinfo is None or after.utcoffset() != timedelta(0):
            raise ValueError("ScheduledRecommendationJob requires an aware UTC datetime")
        minute, hour, day, month, weekday = _cron_fields(self.cron_expression)
        day_is_wildcard: bool = len(day) == 31
        weekday_is_wildcard: bool = len(weekday) == 7
        candidate: datetime = after.astimezone(_KST).replace(second=0, microsecond=0)
        candidate += timedelta(minutes=1)
        for _ in range(527_040):
            cron_weekday: int = (candidate.weekday() + 1) % 7
            day_matches: bool = candidate.day in day
            weekday_matches: bool = cron_weekday in weekday
            date_matches: bool = (
                day_matches and weekday_matches
                if day_is_wildcard or weekday_is_wildcard
                else day_matches or weekday_matches
            )
            if (
                candidate.minute in minute
                and candidate.hour in hour
                and candidate.month in month
                and date_matches
            ):
                return candidate.astimezone(timezone.utc)
            candidate += timedelta(minutes=1)
        raise ValueError("Cron expression has no matching time within one year")
