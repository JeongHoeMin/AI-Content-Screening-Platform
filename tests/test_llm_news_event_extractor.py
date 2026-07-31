from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple, Type, TypeVar

import pytest
from pydantic import BaseModel

from app.extractors import (
    AllExtractionBatchesFailedError,
    DefaultNewsEventParser,
    LLMNewsEventExtractor,
)
from app.llms import (
    ChatMessage,
    ChatRole,
    StructuredOutputCallError,
    StructuredOutputLLM,
    StructuredOutputResponseError,
)
from app.models import (
    Article,
    ArticleInferenceResponseItem,
    BatchExtractionConfig,
    CompanyRelation,
    EventType,
    ExtractedCompanyResponseItem,
    LLMExtractionResult,
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
                        event_type=EventType.CORPORATE_EVENT.value,
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

    assert tuple(inference.article for inference in result.inferences) == articles
    assert result.inferences[0].events[0].title == "Event article-1"
    assert builder.inputs[0].articles is articles
    assert llm.calls == 1


@pytest.mark.anyio
async def test_extractor_splits_batches_and_preserves_global_input_order() -> None:
    articles: Tuple[Article, ...] = tuple(build_article(index) for index in range(21))
    first_batch: Tuple[Article, ...] = articles[:20]
    second_batch: Tuple[Article, ...] = articles[20:]
    extractor, builder, llm = build_extractor(
        [build_response(first_batch), build_response(second_batch)],
        config=BatchExtractionConfig(max_articles_per_batch=20),
    )

    result = await extractor.extract(articles)

    assert tuple(inference.article for inference in result.inferences) == articles
    assert [len(prompt_input.articles) for prompt_input in builder.inputs] == [20, 1]
    assert llm.calls == 2
    assert result.successful_batches == 2


@pytest.mark.anyio
async def test_default_extraction_batch_size_limits_large_structured_responses() -> None:
    articles: Tuple[Article, ...] = tuple(build_article(index) for index in range(50))
    batches: List[Tuple[Article, ...]] = [
        articles[index : index + 10] for index in range(0, len(articles), 10)
    ]
    extractor, builder, llm = build_extractor(
        [build_response(batch) for batch in batches],
    )

    result = await extractor.extract(articles)

    assert [len(prompt_input.articles) for prompt_input in builder.inputs] == [
        10,
        10,
        10,
        10,
        10,
    ]
    assert result.successful_batches == 5
    assert llm.calls == 5


@pytest.mark.anyio
async def test_extractor_records_actual_request_count_for_fifty_articles() -> None:
    articles: Tuple[Article, ...] = tuple(build_article(index) for index in range(50))
    batches: List[Tuple[Article, ...]] = [
        articles[:20],
        articles[20:40],
        articles[40:],
    ]
    extractor, _, llm = build_extractor(
        [build_response(batch) for batch in batches],
        config=BatchExtractionConfig(max_articles_per_batch=20),
    )

    result = await extractor.extract(articles)

    assert len(result.inferences) == 50
    assert result.successful_batches == 3
    assert llm.calls == 3


@pytest.mark.anyio
async def test_extractor_raises_when_every_batch_fails() -> None:
    expected_error: StructuredOutputCallError = StructuredOutputCallError(
        provider="test",
        error_type="APIError",
    )
    articles: Tuple[Article, ...] = (build_article(1),)
    extractor, builder, llm = build_extractor(
        responses=[],
        config=BatchExtractionConfig(max_batch_retry_attempts=0),
        llm_error=expected_error,
    )

    with pytest.raises(AllExtractionBatchesFailedError):
        await extractor.extract(articles)

    assert builder.calls == 1
    assert llm.calls == 1


@pytest.mark.anyio
async def test_extractor_continues_after_one_batch_fails_and_counts_empty_success() -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2))
    empty_response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[
            ArticleInferenceResponseItem(
                article_id=articles[1].id,
                summary="No event",
                reasoning="No meaningful event is stated.",
                confidence=0.9,
                events=[],
            )
        ]
    )
    extractor, _, llm = build_extractor(
        [empty_response],
        config=BatchExtractionConfig(
            max_articles_per_batch=1,
            max_batch_retry_attempts=0,
        ),
    )
    original_generate = llm.generate
    calls: int = 0

    async def generate_with_first_failure(
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise StructuredOutputCallError(
                provider="test",
                error_type="APIConnectionError",
            )
        return await original_generate(messages, response_model)

    llm.generate = generate_with_first_failure  # type: ignore[method-assign]

    result = await extractor.extract(articles)

    assert result.successful_batches == 1
    assert result.inferences[0].article is articles[1]
    assert result.inferences[0].events == ()
    assert len(result.errors) == 1
    assert result.errors[0].kind.value == "api_call"
    assert result.errors[0].message == "test request failed: APIConnectionError"


@pytest.mark.anyio
async def test_extractor_propagates_unexpected_programming_error() -> None:
    articles: Tuple[Article, ...] = (build_article(1),)
    extractor, _, llm = build_extractor(responses=[])
    unexpected_error: RuntimeError = RuntimeError("programming error")

    async def generate_with_unexpected_error(
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        raise unexpected_error

    llm.generate = generate_with_unexpected_error  # type: ignore[method-assign]

    with pytest.raises(RuntimeError) as error_info:
        await extractor.extract(articles)

    assert error_info.value is unexpected_error


@pytest.mark.anyio
async def test_extractor_records_safe_structured_response_reason() -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2))
    empty_response: NewsEventExtractionResponse = NewsEventExtractionResponse(
        articles=[
            ArticleInferenceResponseItem(
                article_id=articles[1].id,
                summary="No event",
                reasoning="No meaningful event is stated.",
                confidence=0.9,
                events=[],
            )
        ]
    )
    extractor, _, llm = build_extractor(
        [empty_response],
        config=BatchExtractionConfig(
            max_articles_per_batch=1,
            max_batch_retry_attempts=0,
        ),
    )
    original_generate = llm.generate
    calls: int = 0

    async def generate_with_response_failure(
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise StructuredOutputResponseError("response_incomplete")
        return await original_generate(messages, response_model)

    llm.generate = generate_with_response_failure  # type: ignore[method-assign]

    result = await extractor.extract(articles)

    assert result.errors[0].kind.value == "response_processing"
    assert result.errors[0].message.endswith("response_incomplete")


@pytest.mark.anyio
async def test_extractor_retries_transient_failed_batch_without_losing_articles() -> None:
    articles: Tuple[Article, ...] = (build_article(1), build_article(2))
    extractor, builder, llm = build_extractor(
        [build_response(articles)],
        config=BatchExtractionConfig(max_articles_per_batch=2),
    )
    original_generate = llm.generate
    calls: int = 0

    async def generate_with_transient_failure(
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise StructuredOutputCallError("test", "APIConnectionError")
        return await original_generate(messages, response_model)

    llm.generate = generate_with_transient_failure  # type: ignore[method-assign]

    result = await extractor.extract(articles)

    assert tuple(inference.article for inference in result.inferences) == articles
    assert result.successful_batches == 1
    assert result.errors == ()
    assert [len(item.articles) for item in builder.inputs] == [2, 2]


@pytest.mark.anyio
async def test_extractor_splits_failed_batch_after_retry_budget_is_disabled() -> None:
    articles: Tuple[Article, ...] = tuple(build_article(index) for index in range(4))
    first_recovery_batch: Tuple[Article, ...] = articles[:2]
    second_recovery_batch: Tuple[Article, ...] = articles[2:]
    extractor, builder, llm = build_extractor(
        [build_response(first_recovery_batch), build_response(second_recovery_batch)],
        config=BatchExtractionConfig(
            max_articles_per_batch=4,
            max_batch_retry_attempts=0,
            recovery_max_articles_per_batch=2,
            max_recovery_requests=2,
        ),
    )
    original_generate = llm.generate
    calls: int = 0

    async def generate_with_initial_response_failure(
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise StructuredOutputResponseError("response_incomplete")
        return await original_generate(messages, response_model)

    llm.generate = generate_with_initial_response_failure  # type: ignore[method-assign]

    result = await extractor.extract(articles)

    assert tuple(inference.article for inference in result.inferences) == articles
    assert result.successful_batches == 1
    assert result.errors == ()
    assert [len(item.articles) for item in builder.inputs] == [4, 2, 2]


@pytest.mark.anyio
async def test_extractor_logs_safe_recovery_trace_without_article_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: List[dict[str, object]] = []

    class CapturingLogger:
        def info(self, event: str, **kwargs: object) -> None:
            records.append({"event": event, **kwargs})

        def warning(self, event: str, **kwargs: object) -> None:
            records.append({"event": event, **kwargs})

    from app.extractors import llm_extractor

    monkeypatch.setattr(llm_extractor, "logger", CapturingLogger())
    article: Article = build_article(1).model_copy(update={"content": "SECRET_ARTICLE_BODY"})
    extractor, _, _ = build_extractor(
        responses=[],
        config=BatchExtractionConfig(max_batch_retry_attempts=0),
        llm_error=StructuredOutputCallError("test", "RateLimitError"),
    )

    with pytest.raises(AllExtractionBatchesFailedError):
        await extractor.extract((article,))

    assert records[0] == {
        "event": "extraction_batch_attempt_started",
        "batch_index": 1,
        "total_batches": 1,
        "article_count": 1,
        "attempt": 1,
        "phase": "initial",
        "max_articles_per_batch": 10,
        "recovery_batch_size": 5,
        "max_batch_retry_attempts": 0,
        "max_recovery_requests": 4,
    }
    assert records[1]["event"] == "extraction_batch_attempt_failed"
    assert records[1]["error_message"] == "test request failed: RateLimitError"
    assert "SECRET_ARTICLE_BODY" not in repr(records)
