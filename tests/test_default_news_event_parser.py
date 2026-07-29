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
