from __future__ import annotations

from typing import List, Tuple

from app.analyzers.base import ImpactAnalyzer
from app.analyzers.policy import ImpactPolicy
from app.analyzers.strategy import ImpactStrategy
from app.models.impact_analysis import ImpactAnalysis, ImpactEvaluation, ImpactObservation
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
            evaluations: Tuple[ImpactEvaluation, ...] = self._policy.evaluate(
                event,
                observations,
            )
            if len(evaluations) != len(observations) or any(
                evaluation.observation is not observation
                for evaluation, observation in zip(evaluations, observations)
            ):
                raise ValueError(
                    "ImpactPolicy evaluations must preserve strategy observation order"
                )
            analyses.append(
                ImpactAnalysis(event=event, evaluations=evaluations)
            )
        return analyses
