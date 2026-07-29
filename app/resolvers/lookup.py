from __future__ import annotations

from typing import Optional, Protocol

from app.models.resolved_news_event import ResolvedTicker


class TickerLookup(Protocol):
    """Resolves a company name to optional market identity information.

    Implementations do not mutate the supplied company name, produce
    deterministic results for identical input, and propagate exceptions
    without wrapping. Name normalization is an internal implementation detail.
    """

    def resolve(self, company_name: str) -> Optional[ResolvedTicker]:
        """Return the resolved ticker, or None when the name is not registered."""
        ...
