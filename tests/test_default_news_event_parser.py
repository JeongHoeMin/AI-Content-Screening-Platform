from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from app.extractors import DefaultNewsEventParser, NewsEventParser
from app.llms import ChatResponse
from app.models import (
    Article,
    ArticleEvaluationResult,
    CompanyRelation,
    NewsEvent,
    NewsEventExtractionResponse,
)


def build_evaluation(is_relevant: bool = True) -> ArticleEvaluationResult:
    return ArticleEvaluationResult(
        article=Article(
            id="article-1",
            title="Samsung expands HBM production",
            content="Samsung Electronics announced an expansion of HBM production.",
            source="Example News",
            published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
            url="https://example.com/articles/1",
        ),
        score=90,
        is_relevant=is_relevant,
        reasons=["Material production expansion"],
    )


def build_event(
    title: str,
    relation: str = "direct",
) -> Dict[str, Any]:
    return {
        "title": title,
        "summary": f"Summary for {title}",
        "companies": [
            {
                "name": "Samsung Electronics",
                "relation": relation,
            }
        ],
        "industries": ["Semiconductors"],
        "keywords": ["HBM"],
        "reasons": ["The production expansion is stated in the article"],
    }


def build_response(events: List[Dict[str, Any]]) -> ChatResponse:
    return ChatResponse(content=json.dumps({"events": events}))


def test_parser_protocol_supports_default_implementation() -> None:
    parser: NewsEventParser = DefaultNewsEventParser()

    assert isinstance(parser, DefaultNewsEventParser)


def test_parser_returns_empty_events_for_valid_empty_response() -> None:
    parser: DefaultNewsEventParser = DefaultNewsEventParser()

    result: List[NewsEvent] = parser.parse(
        build_response([]),
        build_evaluation(is_relevant=False),
    )

    assert result == []


def test_parser_maps_multiple_events_in_response_order() -> None:
    parser: DefaultNewsEventParser = DefaultNewsEventParser()
    response: ChatResponse = build_response(
        [
            build_event("First event", relation="direct"),
            build_event("Second event", relation="indirect"),
        ]
    )

    result: List[NewsEvent] = parser.parse(response, build_evaluation())

    assert [event.title for event in result] == ["First event", "Second event"]
    assert result[0].companies[0].relation is CompanyRelation.DIRECT
    assert result[1].companies[0].relation is CompanyRelation.INDIRECT


def test_parser_creates_domain_objects_separate_from_response_dtos() -> None:
    payload: Dict[str, Any] = {"events": [build_event("Domain event")]}
    response_dto: NewsEventExtractionResponse = (
        NewsEventExtractionResponse.model_validate(payload)
    )
    parser: DefaultNewsEventParser = DefaultNewsEventParser()

    result: List[NewsEvent] = parser.parse(
        ChatResponse(content=json.dumps(payload)),
        build_evaluation(),
    )

    assert result[0] is not response_dto.events[0]
    assert result[0].companies[0] is not response_dto.events[0].companies[0]


def test_parser_propagates_invalid_json() -> None:
    parser: DefaultNewsEventParser = DefaultNewsEventParser()

    with pytest.raises(json.JSONDecodeError):
        parser.parse(ChatResponse(content="not json"), build_evaluation())


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"events": [{"title": "Incomplete"}]},
        {"events": [{**build_event("Extra"), "sentiment": "positive"}]},
        {"events": [build_event("Invalid relation", relation="competitor")]},
        {"events": [], "recommendation": "buy"},
    ],
)
def test_parser_rejects_invalid_contract(payload: Dict[str, Any]) -> None:
    parser: DefaultNewsEventParser = DefaultNewsEventParser()

    with pytest.raises(ValidationError):
        parser.parse(
            ChatResponse(content=json.dumps(payload)),
            build_evaluation(),
        )
