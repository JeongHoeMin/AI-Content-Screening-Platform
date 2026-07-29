from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import pytest

from app.extractors import (
    LLMNewsEventExtractor,
    NewsEventParser,
    NewsEventRequester,
)
from app.llms import ChatMessage, ChatResponse, ChatRole
from app.models import (
    Article,
    ArticleEvaluationResult,
    CompanyRelation,
    ExtractedCompany,
    NewsEvent,
)
from app.prompts import NewsEventPromptInput, PromptBuilder


class FakePromptBuilder(PromptBuilder[NewsEventPromptInput]):
    def __init__(
        self,
        messages: List[ChatMessage],
        call_order: List[str],
        error: Optional[Exception] = None,
    ) -> None:
        self.messages: List[ChatMessage] = messages
        self.call_order: List[str] = call_order
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.received_input: Optional[NewsEventPromptInput] = None

    def build(self, prompt_input: NewsEventPromptInput) -> List[ChatMessage]:
        self.calls += 1
        self.call_order.append("builder")
        self.received_input = prompt_input
        if self.error is not None:
            raise self.error
        return self.messages


class FakeRequester(NewsEventRequester):
    def __init__(
        self,
        response: ChatResponse,
        call_order: List[str],
        error: Optional[Exception] = None,
    ) -> None:
        self.response: ChatResponse = response
        self.call_order: List[str] = call_order
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.received_messages: Optional[List[ChatMessage]] = None

    async def request(self, messages: List[ChatMessage]) -> ChatResponse:
        self.calls += 1
        self.call_order.append("requester")
        self.received_messages = messages
        if self.error is not None:
            raise self.error
        return self.response


class FakeParser(NewsEventParser):
    def __init__(
        self,
        events: List[NewsEvent],
        call_order: List[str],
        error: Optional[Exception] = None,
    ) -> None:
        self.events: List[NewsEvent] = events
        self.call_order: List[str] = call_order
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.received_response: Optional[ChatResponse] = None
        self.received_evaluation: Optional[ArticleEvaluationResult] = None

    def parse(
        self,
        response: ChatResponse,
        evaluation: ArticleEvaluationResult,
    ) -> List[NewsEvent]:
        self.calls += 1
        self.call_order.append("parser")
        self.received_response = response
        self.received_evaluation = evaluation
        if self.error is not None:
            raise self.error
        return self.events


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def build_evaluation() -> ArticleEvaluationResult:
    return ArticleEvaluationResult(
        article=Article(
            id="article-13",
            title="Samsung expands HBM production",
            content="Samsung Electronics announced an HBM production expansion.",
            source="Example News",
            published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
            url="https://example.com/articles/13",
        ),
        score=95,
        is_relevant=True,
        reasons=["Material semiconductor production event"],
    )


def build_messages() -> List[ChatMessage]:
    return [ChatMessage(role=ChatRole.USER, content="Prepared prompt")]


def build_events() -> List[NewsEvent]:
    return [
        NewsEvent(
            title="HBM production expansion",
            summary="Samsung Electronics expands HBM production.",
            companies=[
                ExtractedCompany(
                    name="Samsung Electronics",
                    relation=CompanyRelation.DIRECT,
                )
            ],
            industries=["Semiconductors"],
            keywords=["HBM"],
            reasons=["The expansion is explicitly stated"],
        )
    ]


def build_dependencies(
    builder_error: Optional[Exception] = None,
    requester_error: Optional[Exception] = None,
    parser_error: Optional[Exception] = None,
) -> tuple[FakePromptBuilder, FakeRequester, FakeParser]:
    call_order: List[str] = []
    builder: FakePromptBuilder = FakePromptBuilder(
        messages=build_messages(),
        call_order=call_order,
        error=builder_error,
    )
    requester: FakeRequester = FakeRequester(
        response=ChatResponse(content="raw extraction response"),
        call_order=call_order,
        error=requester_error,
    )
    parser: FakeParser = FakeParser(
        events=build_events(),
        call_order=call_order,
        error=parser_error,
    )
    return builder, requester, parser


def test_constructor_stores_dependencies_without_side_effects() -> None:
    builder, requester, parser = build_dependencies()

    extractor: LLMNewsEventExtractor = LLMNewsEventExtractor(
        requester=requester,
        parser=parser,
        prompt_builder=builder,
    )

    assert extractor._requester is requester
    assert extractor._parser is parser
    assert extractor._prompt_builder is builder
    assert builder.calls == 0
    assert requester.calls == 0
    assert parser.calls == 0


@pytest.mark.anyio
async def test_extractor_orchestrates_in_order_without_copying() -> None:
    evaluation: ArticleEvaluationResult = build_evaluation()
    builder, requester, parser = build_dependencies()
    extractor: LLMNewsEventExtractor = LLMNewsEventExtractor(
        requester=requester,
        parser=parser,
        prompt_builder=builder,
    )

    result: List[NewsEvent] = await extractor.extract(evaluation)

    assert builder.call_order == ["builder", "requester", "parser"]
    assert builder.calls == 1
    assert builder.received_input is not None
    assert builder.received_input.evaluation is evaluation
    assert requester.calls == 1
    assert requester.received_messages is builder.messages
    assert parser.calls == 1
    assert parser.received_response is requester.response
    assert parser.received_evaluation is evaluation
    assert result is parser.events


@pytest.mark.anyio
async def test_extractor_stops_after_prompt_builder_error() -> None:
    expected_error: ValueError = ValueError("prompt build failed")
    builder, requester, parser = build_dependencies(builder_error=expected_error)
    extractor: LLMNewsEventExtractor = LLMNewsEventExtractor(
        requester=requester,
        parser=parser,
        prompt_builder=builder,
    )

    with pytest.raises(ValueError) as error_info:
        await extractor.extract(build_evaluation())

    assert error_info.value is expected_error
    assert builder.calls == 1
    assert requester.calls == 0
    assert parser.calls == 0


@pytest.mark.anyio
async def test_extractor_stops_after_requester_error() -> None:
    expected_error: RuntimeError = RuntimeError("request failed")
    builder, requester, parser = build_dependencies(
        requester_error=expected_error
    )
    extractor: LLMNewsEventExtractor = LLMNewsEventExtractor(
        requester=requester,
        parser=parser,
        prompt_builder=builder,
    )

    with pytest.raises(RuntimeError) as error_info:
        await extractor.extract(build_evaluation())

    assert error_info.value is expected_error
    assert builder.calls == 1
    assert requester.calls == 1
    assert parser.calls == 0


@pytest.mark.anyio
async def test_extractor_propagates_parser_error_without_wrapping() -> None:
    expected_error: ValueError = ValueError("parse failed")
    builder, requester, parser = build_dependencies(parser_error=expected_error)
    extractor: LLMNewsEventExtractor = LLMNewsEventExtractor(
        requester=requester,
        parser=parser,
        prompt_builder=builder,
    )

    with pytest.raises(ValueError) as error_info:
        await extractor.extract(build_evaluation())

    assert error_info.value is expected_error
    assert builder.calls == 1
    assert requester.calls == 1
    assert parser.calls == 1
