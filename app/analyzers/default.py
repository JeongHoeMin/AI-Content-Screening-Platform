from __future__ import annotations

from typing import List, Tuple

from app.analyzers.base import ImpactAnalyzer
from app.analyzers.policy import ImpactPolicy
from app.analyzers.strategy import ImpactStrategy
from app.models.impact_analysis import ImpactAnalysis, ImpactFilterResult, ImpactObservation
from app.models.resolved_news_event import ResolvedNewsEvent


class DefaultImpactAnalyzer(ImpactAnalyzer):
    """Assembles analyses while delegating all impact judgement to a strategy."""

    def __init__(self, strategy: ImpactStrategy, policy: ImpactPolicy) -> None:
        self._strategy: ImpactStrategy = strategy
        self._policy: ImpactPolicy = policy

    def analyze(self, events: List[ResolvedNewsEvent]) -> List[ImpactAnalysis]:
        analyses: List[ImpactAnalysis] = []
        for event in events:
            observations: Tuple[ImpactObservation, ...] = self._strategy.analyze(event)
            filters: Tuple[ImpactFilterResult, ...] = self._policy.filter(
                event,
                observations,
            )
            analyses.append(
                ImpactAnalysis(event=event, observations=observations, filters=filters)
            )
        return analyses
