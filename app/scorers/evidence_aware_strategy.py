from __future__ import annotations

from dataclasses import dataclass
from math import fsum

from app.models.evidence import CompanyEvidence, EvidenceAggregation
from app.models.impact_analysis import CompanyImpact
from app.models.scoring import (
    CompanyScore,
    DirectionScoreEntry,
    ScoreContribution,
    ScoringPolicyConfig,
    ScoringResult,
)
from app.scorers.strategy import ScoringStrategy


@dataclass(frozen=True)
class EvidenceAwareScoringStrategy(ScoringStrategy):
    """Creates the final immutable scoring result from one policy config."""

    config: ScoringPolicyConfig

    def score(self, aggregation: EvidenceAggregation) -> ScoringResult:
        return ScoringResult(
            policy_version=self.config.policy_version,
            companies=tuple(
                self._score_company(evidence) for evidence in aggregation.companies
            ),
        )

    def _score_company(self, evidence: CompanyEvidence) -> CompanyScore:
        contributions: tuple[ScoreContribution, ...] = tuple(
            self._contribution_for(impact) for impact in evidence.impacts
        )
        return CompanyScore(
            company=evidence.company,
            score=fsum(item.value for item in contributions),
            contributions=contributions,
        )

    def _contribution_for(self, impact: CompanyImpact) -> ScoreContribution:
        """Translate one typed CompanyImpact through the injected catalog."""
        entry: DirectionScoreEntry = self.config.catalog.entry_for(impact.direction)
        return ScoreContribution(
            impact=impact,
            factor=entry.factor,
            weight=entry.weight,
            value=entry.weight,
            reason_code=entry.reason_code,
        )
