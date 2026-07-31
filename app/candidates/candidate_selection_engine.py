from __future__ import annotations

from typing import Protocol

from app.models.candidate_selection import CandidateSelectionResult
from app.models.recommendation import RecommendationResult


class CandidateSelectionEngine(Protocol):
    """Returns a candidate selection result through an injected policy."""

    def select(self, recommendation: RecommendationResult) -> CandidateSelectionResult:
        """Return one immutable candidate-selection result."""
        ...
