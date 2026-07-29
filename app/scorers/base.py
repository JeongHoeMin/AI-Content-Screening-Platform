from __future__ import annotations

from typing import Protocol

from app.models.evidence import EvidenceAggregation
from app.models.scoring import ScoringResult


class ScoringEngine(Protocol):
    """Assembles an immutable scoring snapshot through a scoring strategy."""

    def score(self, aggregation: EvidenceAggregation) -> ScoringResult:
        """Return one scoring result without modifying source evidence."""
        ...
