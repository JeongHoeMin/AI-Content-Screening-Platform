from __future__ import annotations

from app.models.evidence import EvidenceAggregation
from app.models.scoring import ScoringResult
from app.scorers.base import ScoringEngine
from app.scorers.strategy import ScoringStrategy


class DefaultScoringEngine(ScoringEngine):
    """Returns the exact immutable result created by an injected strategy."""

    def __init__(self, strategy: ScoringStrategy) -> None:
        self._strategy: ScoringStrategy = strategy

    def score(self, aggregation: EvidenceAggregation) -> ScoringResult:
        return self._strategy.score(aggregation)
