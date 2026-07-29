from __future__ import annotations

from typing import List, Protocol

from app.models.news_event import NewsEvent
from app.models.resolved_news_event import ResolvedNewsEvent


class TickerResolver(Protocol):
    """Builds resolved event snapshots by delegating ticker lookup."""

    def resolve(self, events: List[NewsEvent]) -> List[ResolvedNewsEvent]:
        """Return new resolved snapshots without mutating source events."""
        ...
