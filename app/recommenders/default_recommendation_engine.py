from __future__ import annotations

from app.models.recommendation import RecommendationResult
from app.models.scoring import ScoringResult
from app.recommenders.recommendation_engine import RecommendationEngine
from app.recommenders.recommendation_policy import RecommendationPolicy


class DefaultRecommendationEngine(RecommendationEngine):
    """Assembles recommendation snapshots using only an injected policy.

    Every recommendation decision belongs to the configured
    RecommendationPolicy; the engine owns only orchestration and result
    assembly. It never evaluates recommendation rules directly and returns the
    exact RecommendationResult instance produced by its policy.
    """

    def __init__(self, policy: RecommendationPolicy) -> None:
        self._policy: RecommendationPolicy = policy

    def recommend(self, scoring: ScoringResult) -> RecommendationResult:
        return self._policy.recommend(scoring)
