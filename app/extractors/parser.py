from __future__ import annotations

from typing import Protocol, Tuple

from app.models.article import Article
from app.models.llm_inference import NewsEventParseResult
from app.models.news_event_response import NewsEventExtractionResponse


class NewsEventParser(Protocol):
    """Validates typed LLM output and maps it to inference snapshots."""

    def parse(
        self,
        response: NewsEventExtractionResponse,
        articles: Tuple[Article, ...],
    ) -> NewsEventParseResult:
        """Return ordered valid inferences and recoverable event validation errors."""
        ...
