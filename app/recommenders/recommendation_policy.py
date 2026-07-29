from __future__ import annotations

from typing import Protocol, Tuple

from app.models.recommendation import CompanyRecommendation
from app.models.scoring import ScoringResult


class RecommendationPolicy(Protocol):
    """Creates decisions without creating or replacing CompanyScore objects.

    Implementations treat CompanyScore as an immutable input snapshot. They are
    deterministic and side-effect free, preserving every input CompanyScore
    identity and order while neither mutating scores or evidence nor ranking,
    filtering, performing portfolio analysis, querying market data, or calling
    an LLM.
    """

    def recommend(
        self,
        scoring: ScoringResult,
    ) -> Tuple[CompanyRecommendation, ...]:
        """Return one recommendation for each score in input order."""
        ...
