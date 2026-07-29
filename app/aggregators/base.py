from __future__ import annotations

from typing import List, Protocol

from app.models.evidence import EvidenceAggregation
from app.models.impact_analysis import ImpactAnalysis


class EvidenceAggregator(Protocol):
    """Assembles an immutable evidence snapshot through a grouping strategy."""

    def aggregate(self, analyses: List[ImpactAnalysis]) -> EvidenceAggregation:
        """Return one aggregation without modifying source analyses."""
        ...
