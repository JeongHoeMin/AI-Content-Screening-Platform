from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.analyzers.rule_catalog import ImpactRuleCatalog
from app.analyzers.strategy import ImpactStrategy
from app.models.cross_validation import CrossValidationStatus
from app.models.impact_analysis import ImpactObservation, ImpactScope, ImpactUncertainty
from app.models.news_event import CompanyRelation
from app.models.resolved_news_event import ResolvedNewsEvent


@dataclass(frozen=True)
class RuleImpactStrategy(ImpactStrategy):
    """Creates one fact-level COMPANY observation for every DIRECT company."""

    catalog: ImpactRuleCatalog

    def analyze(self, event: ResolvedNewsEvent) -> Tuple[ImpactObservation, ...]:
        uncertainty: ImpactUncertainty = self._uncertainty_for(event)
        observations: list[ImpactObservation] = []
        for event_fact in event.event.event_facts:
            rule = self.catalog.rule_for(event_fact)
            for company in event.companies:
                if company.relation is not CompanyRelation.DIRECT:
                    continue
                observations.append(
                    ImpactObservation(
                        scope=ImpactScope.COMPANY,
                        company=company,
                        event_fact=event_fact,
                        direction=rule.direction,
                        uncertainty=uncertainty,
                        reason_code=rule.reason_code,
                    )
                )
        return tuple(observations)

    @staticmethod
    def _uncertainty_for(event: ResolvedNewsEvent) -> ImpactUncertainty:
        if event.cross_validation_status is CrossValidationStatus.VERIFIED:
            return ImpactUncertainty.LOW
        if event.cross_validation_status is CrossValidationStatus.PARTIALLY_VERIFIED:
            return ImpactUncertainty.MEDIUM
        return ImpactUncertainty.HIGH
