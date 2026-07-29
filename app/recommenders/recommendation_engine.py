from __future__ import annotations

from typing import Protocol

from app.models.recommendation import RecommendationResult
from app.models.scoring import ScoringResult


class RecommendationEngine(Protocol):
    """Assembles a recommendation snapshot through an injected policy."""

    def recommend(self, scoring: ScoringResult) -> RecommendationResult:
        """Return a recommendation result without modifying policy output."""
        ...
