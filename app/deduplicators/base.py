from __future__ import annotations

from typing import List, Protocol

from app.models.news_event import NewsEvent


class ArticleDeduplicator(Protocol):
    """Removes duplicate events while preserving first-event canonical order."""

    def deduplicate(self, events: List[NewsEvent]) -> List[NewsEvent]:
        """Return first-occurring canonical events without mutating the input."""
        ...
