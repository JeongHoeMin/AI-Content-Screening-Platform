from __future__ import annotations

from typing import Protocol, Tuple

from app.models.article import Article
from app.models.llm_inference import LLMInferenceResult
from app.models.news_event_response import NewsEventExtractionResponse


class NewsEventParser(Protocol):
    """Validates typed LLM output and maps it to inference snapshots."""

    def parse(
        self,
        response: NewsEventExtractionResponse,
        articles: Tuple[Article, ...],
    ) -> Tuple[LLMInferenceResult, ...]:
        """Return one validated inference for every input article in order."""
        ...
