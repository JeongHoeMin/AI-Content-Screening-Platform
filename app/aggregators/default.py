from __future__ import annotations

from typing import List, Tuple

from app.aggregators.base import EvidenceAggregator
from app.aggregators.strategy import AggregationStrategy
from app.models.evidence import CompanyEvidence, EvidenceAggregation
from app.models.impact_analysis import ImpactAnalysis


class DefaultEvidenceAggregator(EvidenceAggregator):
    """Assembles evidence snapshots using only an aggregation strategy."""

    def __init__(self, strategy: AggregationStrategy) -> None:
        self._strategy: AggregationStrategy = strategy

    def aggregate(self, analyses: List[ImpactAnalysis]) -> EvidenceAggregation:
        companies: Tuple[CompanyEvidence, ...] = self._strategy.aggregate(analyses)
        return EvidenceAggregation(companies=companies)
