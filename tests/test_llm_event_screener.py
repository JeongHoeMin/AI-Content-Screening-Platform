from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple, Type, TypeVar

import pytest
from pydantic import BaseModel

from app.llms import ChatMessage, ChatRole, StructuredOutputLLM
from app.models import (
    Article,
    BatchScreeningConfig,
    CompanyRelation,
    ExtractedCompany,
    LLMInferenceResult,
    NewsEvent,
    ScreeningAssessment,
    ScreeningAssessmentResponse,
    ScreeningDecisionType,
)
from app.prompts import BatchScreeningPromptInput, PromptBuilder
from app.screeners import (
    DefaultScreeningAssessmentParser,
    DefaultScreeningPolicy,
    LLMEventScreener,
    ScreeningAssessmentValidationError,
)

OutputT = TypeVar("OutputT", bound=BaseModel)


class FakePromptBuilder(PromptBuilder[BatchScreeningPromptInput]):
    def __init__(self) -> None:
        self.inputs: List[BatchScreeningPromptInput] = []

    def build(self, prompt_input: BatchScreeningPromptInput) -> List[ChatMessage]:
        self.inputs.append(prompt_input)
        return [ChatMessage(role=ChatRole.USER, content="Prepared prompt")]


class FakeStructuredOutputLLM(StructuredOutputLLM):
    def __init__(self, responses: List[ScreeningAssessmentResponse]) -> None:
        self.responses: List[ScreeningAssessmentResponse] = responses
        self.calls: int = 0

    async def generate(
        self,
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        self.calls += 1
        return self.responses.pop(0)  # type: ignore[return-value]


def build_inferences() -> Tuple[LLMInferenceResult, ...]:
    article: Article = Article(
        id="article-1",
        title="Title",
        content="content " * 50,
        source="Example News",
        published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url="https://example.com/articles/1",
    )
    events: Tuple[NewsEvent, ...] = tuple(
        NewsEvent(
            title=f"Event {index}",
            summary="Event summary",
            companies=[
                ExtractedCompany(
                    name="Samsung Electronics",
                    relation=CompanyRelation.DIRECT,
                )
            ],
            industries=["Semiconductors"],
            keywords=["HBM"],
            reasons=["Explicit source fact"],
        )
        for index in range(2)
    )
    return (
        LLMInferenceResult(
            article=article,
            events=events,
            summary="Article summary",
            reasoning="The event is explicitly stated.",
            confidence=0.9,
        ),
    )


def build_screener(
    responses: List[ScreeningAssessmentResponse],
) -> tuple[LLMEventScreener, FakePromptBuilder, FakeStructuredOutputLLM]:
    prompt_builder: FakePromptBuilder = FakePromptBuilder()
    llm: FakeStructuredOutputLLM = FakeStructuredOutputLLM(responses)
    screener: LLMEventScreener = LLMEventScreener(
        structured_llm=llm,
        parser=DefaultScreeningAssessmentParser(),
        prompt_builder=prompt_builder,
        policy=DefaultScreeningPolicy(),
        config=BatchScreeningConfig(),
    )
    return screener, prompt_builder, llm


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_screener_restores_assessment_order_and_preserves_event_identity() -> None:
    inferences: Tuple[LLMInferenceResult, ...] = build_inferences()
    response: ScreeningAssessmentResponse = ScreeningAssessmentResponse(
        assessments=(
            ScreeningAssessment(
                candidate_id="article-1:1",
                relevance=10,
                importance=80,
                credibility=80,
                requires_cross_validation=False,
                reasons=("Irrelevant event",),
            ),
            ScreeningAssessment(
                candidate_id="article-1:0",
                relevance=80,
                importance=80,
                credibility=80,
                requires_cross_validation=False,
                reasons=("Material event",),
            ),
        )
    )
    screener, prompt_builder, llm = build_screener([response])

    decisions = await screener.screen(inferences)

    assert tuple(decision.event for decision in decisions) == inferences[0].events
    assert decisions[0].event is inferences[0].events[0]
    assert decisions[0].decision is ScreeningDecisionType.ACCEPT
    assert decisions[1].decision is ScreeningDecisionType.REJECT
    assert prompt_builder.inputs[0].candidates[0].article is inferences[0].article
    assert llm.calls == 1


@pytest.mark.anyio
async def test_screener_skips_llm_for_empty_events() -> None:
    article: Article = build_inferences()[0].article
    empty_inferences: Tuple[LLMInferenceResult, ...] = (
        LLMInferenceResult(
            article=article,
            events=(),
            summary="No event",
            reasoning="No event was extracted.",
            confidence=0.9,
        ),
    )
    screener, prompt_builder, llm = build_screener([])

    decisions = await screener.screen(empty_inferences)

    assert decisions == ()
    assert prompt_builder.inputs == []
    assert llm.calls == 0


@pytest.mark.anyio
async def test_screener_rejects_missing_or_unknown_assessment_ids() -> None:
    inferences: Tuple[LLMInferenceResult, ...] = build_inferences()
    response: ScreeningAssessmentResponse = ScreeningAssessmentResponse(
        assessments=(
            ScreeningAssessment(
                candidate_id="unknown:0",
                relevance=80,
                importance=80,
                credibility=80,
                requires_cross_validation=False,
                reasons=("Unknown candidate",),
            ),
        )
    )
    screener, _, _ = build_screener([response])

    with pytest.raises(ScreeningAssessmentValidationError):
        await screener.screen(inferences)


@pytest.mark.anyio
async def test_screener_rejects_duplicate_assessment_ids() -> None:
    inferences: Tuple[LLMInferenceResult, ...] = build_inferences()
    response: ScreeningAssessmentResponse = ScreeningAssessmentResponse(
        assessments=(
            ScreeningAssessment(
                candidate_id="article-1:0",
                relevance=80,
                importance=80,
                credibility=80,
                requires_cross_validation=False,
                reasons=("First assessment",),
            ),
            ScreeningAssessment(
                candidate_id="article-1:0",
                relevance=80,
                importance=80,
                credibility=80,
                requires_cross_validation=False,
                reasons=("Duplicate assessment",),
            ),
        )
    )
    screener, _, _ = build_screener([response])

    with pytest.raises(ScreeningAssessmentValidationError):
        await screener.screen(inferences)
