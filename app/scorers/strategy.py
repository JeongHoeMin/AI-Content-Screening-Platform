from __future__ import annotations

from typing import Protocol, Tuple

from app.models.evidence import EvidenceAggregation
from app.models.scoring import CompanyScore


class ScoringStrategy(Protocol):
    """Scores every company evidence while preserving source identity.

    Implementations are deterministic and side-effect free. Each returned
    CompanyScore preserves the identical CompanyEvidence.company object and
    CompanyEvidence.impacts tuple, in input order. Strategies neither skip nor
    duplicate companies, create resolved companies or impacts, mutate inputs,
    nor perform ranking, filtering, recommendation, confidence, time weighting,
    or exception wrapping.
    """

    def score(
        self,
        aggregation: EvidenceAggregation,
    ) -> Tuple[CompanyScore, ...]:
        """Return one immutable score for each input company evidence."""
        ...
