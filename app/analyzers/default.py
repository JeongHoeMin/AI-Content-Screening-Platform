from __future__ import annotations

from typing import List, Tuple

from app.analyzers.base import ImpactAnalyzer
from app.analyzers.strategy import ImpactStrategy
from app.models.impact_analysis import CompanyImpact, ImpactAnalysis
from app.models.resolved_news_event import ResolvedNewsEvent


class DefaultImpactAnalyzer(ImpactAnalyzer):
    """Assembles analyses while delegating all impact judgement to a strategy."""

    def __init__(self, strategy: ImpactStrategy) -> None:
        self._strategy: ImpactStrategy = strategy

    def analyze(self, events: List[ResolvedNewsEvent]) -> List[ImpactAnalysis]:
        analyses: List[ImpactAnalysis] = []
        for event in events:
            impacts: Tuple[CompanyImpact, ...] = self._strategy.analyze(event)
            analyses.append(ImpactAnalysis(event=event, impacts=impacts))
        return analyses
