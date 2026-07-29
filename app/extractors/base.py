from __future__ import annotations

from typing import List, Protocol

from app.models.article import ArticleEvaluationResult
from app.models.news_event import NewsEvent


class NewsEventExtractor(Protocol):
    """Orchestrates news event extraction for one evaluated article."""

    async def extract(
        self,
        evaluation: ArticleEvaluationResult,
    ) -> List[NewsEvent]:
        """Return facts extracted as news events."""
        ...
