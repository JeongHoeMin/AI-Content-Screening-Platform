from __future__ import annotations

from typing import Tuple

from app.extractors.base import NewsEventExtractor
from app.extractors.dart_filing import DartFilingEventAugmenter
from app.models.article import Article
from app.models.llm_inference import LLMExtractionResult


class DartAugmentingNewsEventExtractor(NewsEventExtractor):
    """Runs the injected extractor, then adds narrow official DART observations."""

    def __init__(
        self,
        extractor: NewsEventExtractor,
        augmenter: DartFilingEventAugmenter,
    ) -> None:
        self._extractor: NewsEventExtractor = extractor
        self._augmenter: DartFilingEventAugmenter = augmenter

    async def extract(
        self,
        articles: Tuple[Article, ...],
    ) -> LLMExtractionResult:
        result: LLMExtractionResult = await self._extractor.extract(articles)
        return self._augmenter.augment(result)
