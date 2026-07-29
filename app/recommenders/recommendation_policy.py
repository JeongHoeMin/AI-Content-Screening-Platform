from __future__ import annotations

from typing import Protocol, Tuple

from app.models.recommendation import CompanyRecommendation
from app.models.scoring import ScoringResult


class RecommendationPolicy(Protocol):
    """Creates decisions without creating or replacing CompanyScore objects.

    Implementations are deterministic and side-effect free. They preserve every
    input CompanyScore identity and order while neither mutating scores nor
    ranking, filtering, or reordering companies.
    """

    def recommend(
        self,
        scoring: ScoringResult,
    ) -> Tuple[CompanyRecommendation, ...]:
        """Return one recommendation for each score in input order."""
        ...
