from __future__ import annotations

from typing import List, Protocol

from app.models.impact_analysis import ImpactAnalysis
from app.models.resolved_news_event import ResolvedNewsEvent


class ImpactAnalyzer(Protocol):
    """Assembles immutable impact analyses through an impact strategy."""

    def analyze(self, events: List[ResolvedNewsEvent]) -> List[ImpactAnalysis]:
        """Return analyses while preserving source event order and identity."""
        ...
