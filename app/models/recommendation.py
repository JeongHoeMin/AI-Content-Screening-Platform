from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from app.models.scoring import CompanyScore


class Recommendation(str, Enum):
    """Investment action selected by a recommendation policy."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass(frozen=True)
class CompanyRecommendation:
    """Immutable policy decision for one company.

    The score field preserves the identical CompanyScore instance produced by
    ScoringEngine. CompanyRecommendation never creates, copies, or replaces
    CompanyScore.
    """

    score: CompanyScore
    recommendation: Recommendation


@dataclass(frozen=True)
class RecommendationResult:
    """Immutable recommendation decision snapshot.

    The result preserves the identical CompanyRecommendation instances returned
    by RecommendationPolicy. Their ordering matches the CompanyScore ordering
    from the input ScoringResult, and this snapshot does not modify them.
    """

    companies: Tuple[CompanyRecommendation, ...]
