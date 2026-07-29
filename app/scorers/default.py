from __future__ import annotations

from typing import Tuple

from app.models.evidence import EvidenceAggregation
from app.models.scoring import CompanyScore, ScoringResult
from app.scorers.base import ScoringEngine
from app.scorers.strategy import ScoringStrategy


class DefaultScoringEngine(ScoringEngine):
    """Assembles scoring snapshots using only an injected scoring strategy."""

    def __init__(self, strategy: ScoringStrategy) -> None:
        self._strategy: ScoringStrategy = strategy

    def score(self, aggregation: EvidenceAggregation) -> ScoringResult:
        companies: Tuple[CompanyScore, ...] = self._strategy.score(aggregation)
        return ScoringResult(companies=companies)
