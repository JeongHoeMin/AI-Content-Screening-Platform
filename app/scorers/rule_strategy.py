from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Tuple

from app.models.evidence import CompanyEvidence, EvidenceAggregation
from app.models.impact_analysis import ImpactDirection
from app.models.scoring import CompanyScore
from app.scorers.strategy import ScoringStrategy

_DIRECTION_SCORES: Mapping[ImpactDirection, float] = MappingProxyType(
    {
        ImpactDirection.POSITIVE: 1.0,
        ImpactDirection.NEGATIVE: -1.0,
        ImpactDirection.UNKNOWN: 0.0,
        ImpactDirection.NEUTRAL: 0.0,
    }
)


@dataclass(frozen=True)
class RuleScoringStrategy(ScoringStrategy):
    """Immutable deterministic strategy using the default direction policy.

    The strategy only sums scores supplied by the read-only direction policy.
    It does not rank, filter, weight, recommend, or alter evidence.
    """

    def score(
        self,
        aggregation: EvidenceAggregation,
    ) -> Tuple[CompanyScore, ...]:
        return tuple(
            self._score_company(evidence) for evidence in aggregation.companies
        )

    @staticmethod
    def _score_company(evidence: CompanyEvidence) -> CompanyScore:
        score: float = sum(
            (_DIRECTION_SCORES[impact.direction] for impact in evidence.impacts),
            0.0,
        )
        return CompanyScore(
            company=evidence.company,
            score=score,
            evidences=evidence.impacts,
        )
