from __future__ import annotations

from typing import List, Protocol

from app.models.news_event import NewsEvent
from app.models.resolved_news_event import TickerResolvedEvent


class TickerResolver(Protocol):
    """Assembles immutable resolved event snapshots through Company Resolution.

    Original NewsEvent objects remain unchanged. Company Directory facts and
    Company Resolution Policy determine canonical identities before this
    resolver assembles snapshots. It performs no investment analysis.
    """

    def resolve(self, events: List[NewsEvent]) -> List[TickerResolvedEvent]:
        """Return immutable snapshots without mutating source events."""
        ...
