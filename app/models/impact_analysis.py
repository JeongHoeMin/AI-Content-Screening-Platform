from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from app.models.resolved_news_event import ResolvedCompany, ResolvedNewsEvent


class ImpactDirection(str, Enum):
    """Direction of an event's interpreted impact on a company."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CompanyImpact:
    """Impact direction associated with one resolved company."""

    company: ResolvedCompany
    direction: ImpactDirection


@dataclass(frozen=True)
class ImpactAnalysis:
    """Immutable analysis snapshot produced from one resolved news event.

    UNKNOWN represents insufficient grounds to determine a direction. NEUTRAL
    represents an affirmative determination of no impact.
    """

    event: ResolvedNewsEvent
    impacts: Tuple[CompanyImpact, ...]
