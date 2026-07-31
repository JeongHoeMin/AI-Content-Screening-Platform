from __future__ import annotations

from typing import Protocol

from app.models.candidate_selection import CandidateSelectionResult
from app.models.recommendation import RecommendationResult


class CandidateSelectionPolicy(Protocol):
    """Deterministically evaluates recommendation decisions without mutation."""

    def select(self, recommendation: RecommendationResult) -> CandidateSelectionResult:
        """Return the final immutable selection result in input audit order."""
        ...
