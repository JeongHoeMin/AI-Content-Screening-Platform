from __future__ import annotations

from typing import Tuple

from app.models.recommendation import CompanyRecommendation, RecommendationResult
from app.models.scoring import ScoringResult
from app.recommenders.recommendation_engine import RecommendationEngine
from app.recommenders.recommendation_policy import RecommendationPolicy


class DefaultRecommendationEngine(RecommendationEngine):
    """Assembles recommendation snapshots using only an injected policy."""

    def __init__(self, policy: RecommendationPolicy) -> None:
        self._policy: RecommendationPolicy = policy

    def recommend(self, scoring: ScoringResult) -> RecommendationResult:
        companies: Tuple[CompanyRecommendation, ...] = self._policy.recommend(scoring)
        return RecommendationResult(companies=companies)
