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
    DEFAULT_EVENT_TYPE_COMPATIBILITY,
    EventFact,
    EventType,
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
        event_type=EventType.CORPORATE_EVENT,
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
        "event_type": EventType.CORPORATE_EVENT,
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


def test_news_event_requires_event_type() -> None:
    values: Dict[str, Any] = {
        "title": "Event",
        "summary": "Summary",
        "companies": [],
        "industries": [],
        "keywords": [],
        "reasons": [],
    }

    with pytest.raises(ValidationError):
        NewsEvent.model_validate(values)


def test_news_event_preserves_fact_order_and_deduplicates_facts() -> None:
    event: NewsEvent = NewsEvent(
        title="Expansion",
        summary="Factory expansion and layoffs are announced.",
        event_type=EventType.CORPORATE_EVENT,
        event_facts=(
            EventFact.FACTORY_EXPANSION,
            EventFact.MASS_LAYOFF,
            EventFact.FACTORY_EXPANSION,
        ),
        companies=[],
        industries=[],
        keywords=[],
        reasons=[],
    )

    assert event.event_facts == (
        EventFact.FACTORY_EXPANSION,
        EventFact.MASS_LAYOFF,
    )


def test_event_type_compatibility_is_independent_of_event_fact_enum() -> None:
    assert DEFAULT_EVENT_TYPE_COMPATIBILITY.is_compatible(
        EventType.FINANCIAL_EVENT,
        EventFact.BANKRUPTCY,
    )
    assert not DEFAULT_EVENT_TYPE_COMPATIBILITY.is_compatible(
        EventType.PRODUCT_EVENT,
        EventFact.FACTORY_EXPANSION,
    )

    event: NewsEvent = NewsEvent(
        title="Product launch",
        summary="A product is released.",
        event_type=EventType.PRODUCT_EVENT,
        event_facts=(EventFact.FACTORY_EXPANSION,),
        companies=[],
        industries=[],
        keywords=[],
        reasons=[],
    )

    assert event.event_facts == (EventFact.FACTORY_EXPANSION,)
