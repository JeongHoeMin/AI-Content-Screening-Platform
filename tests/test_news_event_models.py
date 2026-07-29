from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import pytest
from pydantic import ValidationError

from app.extractors import NewsEventExtractor
from app.models import (
    Article,
    ArticleRejectReason,
    CompanyRelation,
    ExtractedCompany,
    LLMInferenceResult,
    LLMExtractionResult,
    NewsEvent,
)


def build_article() -> Article:
    return Article(
        id="article-1",
        title="Samsung expands HBM production",
        content="Samsung announced an expansion." * 20,
        source="Example News",
        published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url="https://example.com/articles/1",
    )


class FakeNewsEventExtractor(NewsEventExtractor):
    async def extract(self, articles: Tuple[Article, ...]) -> LLMExtractionResult:
        return LLMExtractionResult(inferences=(), successful_batches=0)


def test_article_reject_reason_uses_observable_values() -> None:
    assert list(ArticleRejectReason) == [
        ArticleRejectReason.EMPTY_TITLE,
        ArticleRejectReason.EMPTY_BODY,
        ArticleRejectReason.BODY_TOO_SHORT,
    ]


def test_news_event_extractor_protocol_supports_batch_implementation() -> None:
    extractor: NewsEventExtractor = FakeNewsEventExtractor()

    assert isinstance(extractor, FakeNewsEventExtractor)


def test_llm_inference_confidence_is_bounded() -> None:
    event: NewsEvent = NewsEvent(
        title="HBM production expansion",
        summary="Samsung Electronics expands HBM production.",
        companies=[],
        industries=["Semiconductors"],
        keywords=["HBM"],
        reasons=["The expansion is stated"],
    )

    with pytest.raises(ValidationError):
        LLMInferenceResult(
            article=build_article(),
            events=(event,),
            summary="Summary",
            reasoning="Readable rationale.",
            confidence=1.1,
        )


@pytest.mark.parametrize("field_name", ["industries", "keywords", "reasons"])
def test_news_event_rejects_empty_collection_items(field_name: str) -> None:
    values: Dict[str, Any] = {
        "title": "HBM production expansion",
        "summary": "Samsung Electronics expands HBM production.",
        "companies": [
            ExtractedCompany(
                name="Samsung Electronics",
                relation=CompanyRelation.DIRECT,
            )
        ],
        "industries": ["Semiconductors"],
        "keywords": ["HBM"],
        "reasons": ["The expansion is stated in the article"],
    }
    values[field_name] = [""]

    with pytest.raises(ValidationError):
        NewsEvent.model_validate(values)
