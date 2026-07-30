from __future__ import annotations

from typing import Protocol, Tuple

from app.models.impact_analysis import ImpactObservation
from app.models.resolved_news_event import ResolvedNewsEvent


class ImpactStrategy(Protocol):
    """Determines one impact direction for every company in an event.

    Implementations are deterministic and side-effect free. They preserve the
    input company order and identity, do not mutate the input event, and
    propagate exceptions without wrapping.
    """

    def analyze(self, event: ResolvedNewsEvent) -> Tuple[ImpactObservation, ...]:
        """Return fact-level observations in source fact and company order."""
        ...
