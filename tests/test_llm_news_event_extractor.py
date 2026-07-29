from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple, Type, TypeVar

import pytest
from pydantic import BaseModel

from app.extractors import DefaultNewsEventParser, LLMNewsEventExtractor
from app.llms import ChatMessage, ChatRole, StructuredOutputLLM
from app.models import (
    Article,
    ArticleInferenceResponseItem,
    BatchExtractionConfig,
    CompanyRelation,
    ExtractedCompanyResponseItem,
    NewsEventExtractionResponse,
    NewsEventResponseItem,
)
from app.prompts import BatchNewsEventPromptInput, PromptBuilder

OutputT = TypeVar("OutputT", bound=BaseModel)


class FakePromptBuilder(PromptBuilder[BatchNewsEventPromptInput]):
    def __init__(self, error: Optional[Exception] = None) -> None:
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.inputs: List[BatchNewsEventPromptInput] = []

    def build(self, prompt_input: BatchNewsEventPromptInput) -> List[ChatMessage]:
        self.calls += 1
        self.inputs.append(prompt_input)
        if self.error is not None:
            raise self.error
        return [ChatMessage(role=ChatRole.USER, content="Prepared prompt")]


class FakeStructuredOutputLLM(StructuredOutputLLM):
    def __init__(
        self,
        responses: List[NewsEventExtractionResponse],
        error: Optional[Exception] = None,
    ) -> None:
        self.responses: List[NewsEventExtractionResponse] = responses
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.received_messages: List[List[ChatMessage]] = []

    async def generate(
        self,
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        self.calls += 1
        self.received_messages.append(messages)
        if self.error is not None:
            raise self.error
        return self.responses.pop(0)  # type: ignore[return-value]


def build_article(index: int) -> Article:
    return Article(
        id=f"article-{index}",
        title=f"Title {index}",
        content="content " * 50,
        source="Example News",
        published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url=f"https://example.com/articles/{index}",
    )


def build_response(articles: Tuple[Article, ...]) -> NewsEventExtractionResponse:
    return NewsEventExtractionResponse(
        articles=[
            ArticleInferenceResponseItem(
                article_id=article.id,
                summary=f"Summary {article.id}",
                reasoning="The article explicitly states the event.",
                confidence=0.9,
                events=[
                    NewsEventResponseItem(
                        title=f"Event {article.id}",
                        summary="Event summary",
                        companies=[
                            ExtractedCompanyResponseItem(
                                name="Samsung Electronics",
                                relation=CompanyRelation.DIRECT,
                            )
                        ],
                        industries=["Semiconductors"],
                        keywords=["HBM"],
                        reasons=["The article states the event"],
                    )
                ],
            )
            for article in articles
        ]
    )


def build_extractor(
    responses: List[NewsEventExtractionResponse],
    config: BatchExtractionConfig = BatchExtractionConfig(),
    llm_error: Optional[Exception] = None,
) -> tuple[LLMNewsEventExtractor, FakePromptBuilder, FakeStructuredOutputLLM]:
    builder: FakePromptBuilder = FakePromptBuilder()
    llm: FakeStructuredOutputLLM = FakeStructuredOutputLLM(responses, llm_error)
    extractor: LLMNewsEventExtractor = LLMNewsEventExtractor(
        structured_llm=llm,
        parser=DefaultNewsEventParser(),
        prompt_builder=builder,
        config=config,
    )
    return extractor, builder, llm


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_extractor_returns_ordered_inferences_for_one_batch() -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2))
    extractor, builder, llm = build_extractor([build_response(articles)])

    result = await extractor.extract(articles)

    assert tuple(inference.article for inference in result) == articles
    assert result[0].events[0].title == "Event article-1"
    assert builder.inputs[0].articles is articles
    assert llm.calls == 1


@pytest.mark.anyio
async def test_extractor_splits_batches_and_preserves_global_input_order() -> None:
    articles: Tuple[Article, ...] = tuple(build_article(index) for index in range(21))
    first_batch: Tuple[Article, ...] = articles[:20]
    second_batch: Tuple[Article, ...] = articles[20:]
    extractor, builder, llm = build_extractor(
        [build_response(first_batch), build_response(second_batch)],
        config=BatchExtractionConfig(max_articles_per_request=20),
    )

    result = await extractor.extract(articles)

    assert tuple(inference.article for inference in result) == articles
    assert [len(prompt_input.articles) for prompt_input in builder.inputs] == [20, 1]
    assert llm.calls == 2


@pytest.mark.anyio
async def test_extractor_propagates_structured_llm_error_without_wrapping() -> None:
    expected_error: RuntimeError = RuntimeError("LLM failed")
    articles: Tuple[Article, ...] = (build_article(1),)
    extractor, builder, llm = build_extractor(
        responses=[],
        llm_error=expected_error,
    )

    with pytest.raises(RuntimeError) as error_info:
        await extractor.extract(articles)

    assert error_info.value is expected_error
    assert builder.calls == 1
    assert llm.calls == 1
