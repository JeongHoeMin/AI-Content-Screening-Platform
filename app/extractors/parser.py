from __future__ import annotations

from typing import List, Protocol

from app.llms.models import ChatResponse
from app.models.article import ArticleEvaluationResult
from app.models.news_event import NewsEvent


class NewsEventParser(Protocol):
    """Converts an LLM response into news event domain values."""

    def parse(
        self,
        response: ChatResponse,
        evaluation: ArticleEvaluationResult,
    ) -> List[NewsEvent]:
        """Decode, validate, and map one extraction response."""
        ...
