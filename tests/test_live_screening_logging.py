from __future__ import annotations

import asyncio

import pytest

from app.llms.errors import StructuredOutputCallError
from app.models import (
    Article,
    BatchScreeningConfig,
    EventType,
    LLMInferenceResult,
    NewsEvent,
)
from app.prompts import ScreeningPromptBuilder
from app.screeners import DefaultScreeningAssessmentParser, DefaultScreeningPolicy, LLMEventScreener
from app.screeners.errors import NoValidScreeningDecisionsError


class FailingStructuredOutputLlm:
    async def generate(self, messages: object, response_model: object) -> object:
        raise StructuredOutputCallError("openai", "BadRequestError")


def test_screening_logs_safe_provider_error_type_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[dict[str, object]] = []

    class CapturingLogger:
        def warning(self, event: str, **kwargs: object) -> None:
            records.append({"event": event, **kwargs})

    from app.screeners import llm_screener

    monkeypatch.setattr(llm_screener, "logger", CapturingLogger())
    screener: LLMEventScreener = LLMEventScreener(
        FailingStructuredOutputLlm(),
        DefaultScreeningAssessmentParser(),
        ScreeningPromptBuilder(),
        DefaultScreeningPolicy(),
        BatchScreeningConfig(),
    )
    article: Article = Article(id="article", title="title", content="content", source="source", published_at="2026-07-30T00:00:00Z", url="https://example.com")
    event: NewsEvent = NewsEvent(
        title="event",
        summary="summary",
        event_type=EventType.CORPORATE_EVENT,
        companies=[],
        industries=[],
        keywords=["keyword"],
        reasons=["reason"],
    )
    inference: LLMInferenceResult = LLMInferenceResult(
        article=article,
        events=(event,),
        summary="summary",
        reasoning="reasoning",
        confidence=0.9,
    )
    with pytest.raises(NoValidScreeningDecisionsError):
        asyncio.run(screener.screen((inference,)))

    assert records == [{
        "event": "screening_batch_failed",
        "batch_index": 0,
        "candidate_count": 1,
        "error_kind": "structured_output_call",
        "provider": "openai",
        "provider_error_type": "BadRequestError",
    }]
