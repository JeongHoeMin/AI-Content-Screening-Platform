from __future__ import annotations

from typing import Protocol, Tuple

from app.models.article import Article
from app.models.llm_inference import LLMExtractionResult


class NewsEventExtractor(Protocol):
    """Extracts immutable LLM inference snapshots for accepted article batches."""

    async def extract(
        self,
        articles: Tuple[Article, ...],
    ) -> LLMExtractionResult:
        """Return ordered inference snapshots and actual LLM request count."""
        ...
