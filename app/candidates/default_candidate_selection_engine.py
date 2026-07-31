from __future__ import annotations

from app.candidates.candidate_selection_engine import CandidateSelectionEngine
from app.candidates.candidate_selection_policy import CandidateSelectionPolicy
from app.models.candidate_selection import CandidateSelectionResult
from app.models.recommendation import RecommendationResult


class DefaultCandidateSelectionEngine(CandidateSelectionEngine):
    """Delegates once and returns the exact result created by its policy."""

    def __init__(self, policy: CandidateSelectionPolicy) -> None:
        self._policy: CandidateSelectionPolicy = policy

    def select(self, recommendation: RecommendationResult) -> CandidateSelectionResult:
        return self._policy.select(recommendation)
