from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from app.models.news_event import CompanyRelation, NewsEvent


@dataclass(frozen=True)
class ResolvedTicker:
    """Market identity resolved for a company.

    This value does not imply that the ticker is valid, listed, or tradable.
    It contains no market data, investment analysis, or recommendation.
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
class ResolvedNewsEvent:
    """Immutable snapshot produced by the ticker resolution stage.

    The original event remains the source of truth for all event metadata.
    Resolution augments company identity only, and later stages consume this
    snapshot without modifying it.
    """

    event: NewsEvent
    companies: Tuple[ResolvedCompany, ...]
