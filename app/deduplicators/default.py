from __future__ import annotations

from typing import List

from app.deduplicators.base import ArticleDeduplicator
from app.deduplicators.strategy import DuplicateStrategy
from app.models.news_event import NewsEvent


class DefaultArticleDeduplicator(ArticleDeduplicator):
    """Eliminates duplicates by delegating all duplicate decisions to a strategy."""

    def __init__(self, strategy: DuplicateStrategy) -> None:
        self._strategy: DuplicateStrategy = strategy

    def deduplicate(self, events: List[NewsEvent]) -> List[NewsEvent]:
        canonical_events: List[NewsEvent] = []
        for event in events:
            is_duplicate: bool = any(
                self._strategy.is_duplicate(event, canonical_event)
                for canonical_event in canonical_events
            )
            if is_duplicate:
                continue
            canonical_events.append(event)
        return canonical_events
