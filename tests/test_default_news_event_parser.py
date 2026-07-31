from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

import pytest

from app.extractors import (
    DefaultNewsEventParser,
    InferenceResultValidationError,
    NewsEventParser,
)
from app.models import (
    Article,
    ArticleInferenceResponseItem,
    CompanyRelation,
    EventFact,
    EventType,
    EventTypeCompatibility,
    EventTypeCompatibilityEntry,
    ExtractionErrorKind,
    ExtractedCompanyResponseItem,
    NewsEventExtractionResponse,
    NewsEventResponseItem,
)


def build_article(index: int) -> Article:
    return Article(
        id=f"article-{index}",
        title=f"Title {index}",
        content="content " * 50,
        source="Example News",
        published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url=f"https://example.com/articles/{index}",
    )


def build_item(article_id: str, title: str) -> ArticleInferenceResponseItem:
    return ArticleInferenceResponseItem(
        article_id=article_id,
        summary=f"Summary for {title}",
        reasoning="The event is directly stated in the source article.",
        confidence=0.8,
        events=[
            NewsEventResponseItem(
                title=title,
                summary=f"Event summary for {title}",
                event_type=EventType.CORPORATE_EVENT.value,
                companies=[
                    ExtractedCompanyResponseItem(
                        name="Samsung Electronics",
                        relation=CompanyRelation.DIRECT,
                    )
                ],
                industries=["Semiconductors"],
                keywords=["HBM"],
                reasons=["The event is explicitly stated"],
            )
        ],
    )


def test_parser_protocol_supports_default_implementation() -> None:
    parser: NewsEventParser = DefaultNewsEventParser()

    assert isinstance(parser, DefaultNewsEventParser)


def test_parser_preserves_input_article_order_and_event_identity() -> None:
    first_article: Article = build_article(1)
    second_article: Article = build_article(2)
    response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[
            build_item(second_article.id, "Second event"),
            build_item(first_article.id, "First event"),
        ]
    )
    parser: DefaultNewsEventParser = DefaultNewsEventParser()

    result = parser.parse(response, (first_article, second_article))

    assert tuple(inference.article for inference in result.inferences) == (
        first_article,
        second_article,
    )
    assert result.inferences[0].article is first_article
    assert result.inferences[0].events[0].title == "First event"
    assert result.inferences[1].events[0].companies[0].relation is CompanyRelation.DIRECT
    assert result.inferences[0].confidence == 0.8


@pytest.mark.parametrize(
    "response_articles",
    [
        [],
        [build_item("article-1", "One"), build_item("article-1", "Duplicate")],
        [build_item("unknown", "Unknown")],
    ],
)
def test_parser_rejects_missing_unknown_or_duplicate_article_ids(
    response_articles: List[ArticleInferenceResponseItem],
) -> None:
    parser: DefaultNewsEventParser = DefaultNewsEventParser()
    response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=response_articles
    )

    with pytest.raises(InferenceResultValidationError):
        parser.parse(response, (build_article(1),))


def test_parser_rejects_duplicate_input_article_ids() -> None:
    article: Article = build_article(1)
    response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[build_item(article.id, "One")]
    )
    parser: DefaultNewsEventParser = DefaultNewsEventParser()

    with pytest.raises(InferenceResultValidationError):
        parser.parse(response, (article, article))


def test_parser_keeps_valid_events_when_a_sibling_event_is_invalid() -> None:
    article: Article = build_article(1)
    response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[
            ArticleInferenceResponseItem(
                article_id=article.id,
                summary="Article summary",
                reasoning="Article reasoning",
                confidence=0.8,
                events=[
                    NewsEventResponseItem(
                        title="  Valid event  ",
                        summary="  Valid summary  ",
                        event_type=EventType.CORPORATE_EVENT.value,
                        companies=[
                            ExtractedCompanyResponseItem(
                                name=" Example Corp ",
                                relation="direct",
                            ),
                            ExtractedCompanyResponseItem(
                                name="example corp",
                                relation="direct",
                            ),
                        ],
                        industries=[" AI ", "ai", ""],
                        keywords=[" Chips ", "chips"],
                        reasons=[" Stated in article ", "Stated in article"],
                    ),
                    NewsEventResponseItem(
                        title=" ",
                        summary="Invalid event",
                        event_type=EventType.CORPORATE_EVENT.value,
                    ),
                ],
            )
        ]
    )

    result = DefaultNewsEventParser().parse(response, (article,))

    event = result.inferences[0].events[0]
    assert len(result.inferences[0].events) == 1
    assert event.title == "Valid event"
    assert [company.name for company in event.companies] == ["Example Corp"]
    assert event.industries == ["AI"]
    assert event.keywords == ["Chips"]
    assert event.reasons == ["Stated in article"]
    assert len(result.errors) == 1


def test_parser_keeps_valid_facts_and_records_fact_local_errors() -> None:
    article: Article = build_article(1)
    response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[
            ArticleInferenceResponseItem(
                article_id=article.id,
                summary="Article summary",
                reasoning="Article reasoning",
                confidence=0.8,
                events=[
                    NewsEventResponseItem(
                        title="Expansion",
                        summary="An expansion is announced.",
                        event_type=EventType.CORPORATE_EVENT.value,
                        event_facts=[
                            EventFact.FACTORY_EXPANSION.value,
                            "not_a_fact",
                            EventFact.PRODUCT_RELEASE.value,
                            EventFact.FACTORY_EXPANSION.value,
                        ],
                    )
                ],
            )
        ]
    )

    result = DefaultNewsEventParser().parse(response, (article,))

    assert result.inferences[0].events[0].event_facts == (
        EventFact.FACTORY_EXPANSION,
    )
    assert [error.kind for error in result.errors] == [
        ExtractionErrorKind.FACT_VALIDATION,
        ExtractionErrorKind.FACT_VALIDATION,
    ]
    assert [error.fact_index for error in result.errors] == [1, 2]


def test_parser_preserves_explicit_major_supply_contract_fact() -> None:
    article: Article = build_article(1)
    response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[
            ArticleInferenceResponseItem(
                article_id=article.id,
                summary="Article summary",
                reasoning="Article reasoning",
                confidence=0.8,
                events=[
                    NewsEventResponseItem(
                        title="Supply contract",
                        summary="Example Corp entered a supply contract.",
                        event_type=EventType.FINANCIAL_EVENT.value,
                        event_facts=[EventFact.MAJOR_SUPPLY_CONTRACT.value],
                        companies=[
                            ExtractedCompanyResponseItem(
                                name="Example Corp",
                                relation=CompanyRelation.DIRECT.value,
                            )
                        ],
                    )
                ],
            )
        ]
    )

    result = DefaultNewsEventParser().parse(response, (article,))

    assert result.errors == ()
    assert result.inferences[0].events[0].event_facts == (
        EventFact.MAJOR_SUPPLY_CONTRACT,
    )


def test_parser_excludes_event_with_invalid_event_type() -> None:
    article: Article = build_article(1)
    response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[
            ArticleInferenceResponseItem(
                article_id=article.id,
                summary="Article summary",
                reasoning="Article reasoning",
                confidence=0.8,
                events=[
                    NewsEventResponseItem(
                        title="Unknown category",
                        summary="Event summary.",
                        event_type="unknown_event_type",
                    )
                ],
            )
        ]
    )

    result = DefaultNewsEventParser().parse(response, (article,))

    assert result.inferences[0].events == ()
    assert result.errors[0].kind is ExtractionErrorKind.EVENT_VALIDATION


def test_parser_uses_injected_event_type_compatibility_table() -> None:
    article: Article = build_article(1)
    compatibility: EventTypeCompatibility = EventTypeCompatibility(
        entries=(
            EventTypeCompatibilityEntry(
                event_type=EventType.PRODUCT_EVENT,
                event_facts=(EventFact.FACTORY_EXPANSION,),
            ),
            EventTypeCompatibilityEntry(
                event_type=EventType.CORPORATE_EVENT,
                event_facts=(
                    EventFact.MASS_LAYOFF,
                    EventFact.CEO_INTERVIEW,
                ),
            ),
            EventTypeCompatibilityEntry(
                event_type=EventType.FINANCIAL_EVENT,
                event_facts=(
                    EventFact.BANKRUPTCY,
                    EventFact.MAJOR_SUPPLY_CONTRACT,
                ),
            ),
            EventTypeCompatibilityEntry(
                event_type=EventType.MACRO_EVENT,
                event_facts=(EventFact.PRODUCT_RELEASE,),
            ),
        )
    )
    response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[
            ArticleInferenceResponseItem(
                article_id=article.id,
                summary="Article summary",
                reasoning="Article reasoning",
                confidence=0.8,
                events=[
                    NewsEventResponseItem(
                        title="Expansion",
                        summary="An expansion is announced.",
                        event_type=EventType.PRODUCT_EVENT.value,
                        event_facts=[EventFact.FACTORY_EXPANSION.value],
                    )
                ],
            )
        ]
    )

    result = DefaultNewsEventParser(compatibility).parse(response, (article,))

    assert result.errors == ()
    assert result.inferences[0].events[0].event_facts == (
        EventFact.FACTORY_EXPANSION,
    )


def test_parser_normalizes_article_level_summary_and_reasoning() -> None:
    article: Article = build_article(1)
    response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[
            ArticleInferenceResponseItem(
                article_id=article.id,
                summary="  Article\n summary  ",
                reasoning="  Extracted\tfrom article  ",
                confidence=0.8,
                events=[],
            )
        ]
    )

    result = DefaultNewsEventParser().parse(response, (article,))

    assert result.inferences[0].summary == "Article summary"
    assert result.inferences[0].reasoning == "Extracted from article"
