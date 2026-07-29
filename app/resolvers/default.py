from __future__ import annotations

from typing import List, Tuple

from app.models.news_event import ExtractedCompany, NewsEvent
from app.models.resolved_news_event import ResolvedCompany, ResolvedNewsEvent
from app.resolvers.base import TickerResolver
from app.resolvers.lookup import TickerLookup


class DefaultTickerResolver(TickerResolver):
    """Builds immutable resolution snapshots using only a ticker lookup."""

    def __init__(self, lookup: TickerLookup) -> None:
        self._lookup: TickerLookup = lookup

    def resolve(self, events: List[NewsEvent]) -> List[ResolvedNewsEvent]:
        return [
            ResolvedNewsEvent(
                event=event,
                companies=self._resolve_companies(event.companies),
            )
            for event in events
        ]

    def _resolve_companies(
        self,
        companies: List[ExtractedCompany],
    ) -> Tuple[ResolvedCompany, ...]:
        return tuple(
            ResolvedCompany(
                name=company.name,
                relation=company.relation,
                ticker=self._lookup.resolve(company.name),
            )
            for company in companies
        )
