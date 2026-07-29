from __future__ import annotations

from typing import List, Protocol

from app.models.news_event import NewsEvent
from app.models.resolved_news_event import ResolvedNewsEvent


class TickerResolver(Protocol):
    """Assembles immutable resolved event snapshots through ticker lookup.

    Original NewsEvent objects remain unchanged. Ticker resolution is delegated
    entirely to TickerLookup, while this resolver only assembles resolved domain
    models and performs no investment analysis.
    """

    def resolve(self, events: List[NewsEvent]) -> List[ResolvedNewsEvent]:
        """Return immutable snapshots without mutating source events."""
        ...
