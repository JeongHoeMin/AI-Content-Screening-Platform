from __future__ import annotations

from typing import Protocol

from app.models.evidence import EvidenceAggregation
from app.models.scoring import ScoringResult


class ScoringStrategy(Protocol):
    """Scores every company evidence while preserving source identity.

    Implementations are deterministic and side-effect free. Each returned
    ScoringResult preserves input company order and evidence identity through
    CompanyScore contributions. Strategies neither skip nor duplicate companies,
    create resolved companies or impacts, mutate inputs,
    nor perform ranking, filtering, recommendation, confidence, time weighting,
    or exception wrapping.
    """

    def score(
        self,
        aggregation: EvidenceAggregation,
    ) -> ScoringResult:
        """Return the final immutable scoring result for the aggregation."""
        ...
