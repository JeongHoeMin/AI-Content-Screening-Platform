from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from app.models.cross_validation import CrossValidationStatus
from app.models.screening import ScreeningDecisionType

from app.models.news_event import CompanyRelation, NewsEvent


@dataclass(frozen=True)
class ResolvedTicker:
    """Market identity resolved for a company.

    This value does not imply that the ticker is valid, listed, or tradable.
    It contains no market data, investment analysis, or recommendation.
    Future lookup implementations may resolve additional market identifiers
    while preserving this domain responsibility.
    """

    ticker: str
    exchange: str


@dataclass(frozen=True)
class ResolvedCompany:
    """Original company identity augmented with an optional ticker resolution."""

    name: str
    relation: CompanyRelation
    ticker: Optional[ResolvedTicker]


@dataclass(frozen=True)
class TickerResolvedEvent:
    """Immutable snapshot produced by the ticker resolution stage.

    The original event remains the source of truth for all event metadata.
    Resolution augments company identity only, and later stages consume this
    snapshot without modifying it.
    """

    event: NewsEvent
    companies: Tuple[ResolvedCompany, ...]


class ResolvedDecisionType(str, Enum):
    ACCEPT = "accept"
    REVIEW = "review"
    REJECT = "reject"


@dataclass(frozen=True)
class ResolvedNewsEvent:
    """Final immutable event containing resolution decision and ticker data."""

    event: NewsEvent
    companies: Tuple[ResolvedCompany, ...]
    screening_decision: ScreeningDecisionType = ScreeningDecisionType.REVIEW
    cross_validation_status: Optional[CrossValidationStatus] = None
    decision: ResolvedDecisionType = ResolvedDecisionType.REVIEW
    reasons: Tuple[str, ...] = ()
