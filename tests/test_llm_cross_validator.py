from __future__ import annotations

from typing import List, Tuple, Type, TypeVar

import pytest
from pydantic import BaseModel

from app.cross_validators import DefaultCrossValidationAssessmentParser, DefaultCrossValidationPolicy, LLMEventCrossValidator, NoValidCrossValidationResultsError
from app.llms import ChatMessage, ChatRole, StructuredOutputCallError, StructuredOutputLLM
from app.models import BatchCrossValidationConfig, CrossValidationAssessmentResponse, CrossValidationAssessmentResponseItem, CrossValidationEvidenceResponseItem, CrossValidationCandidate
from app.prompts import BatchCrossValidationPromptInput, PromptBuilder
from tests.test_cross_validation_policy import article, candidate

OutputT = TypeVar("OutputT", bound=BaseModel)


class FakePromptBuilder(PromptBuilder[BatchCrossValidationPromptInput]):
    def build(self, prompt_input: BatchCrossValidationPromptInput) -> List[ChatMessage]:
        return [ChatMessage(role=ChatRole.USER, content="prompt")]


class FakeLLM(StructuredOutputLLM):
    def __init__(self, responses: List[CrossValidationAssessmentResponse]) -> None:
        self.responses = responses
        self.calls = 0

    async def generate(self, messages: List[ChatMessage], response_model: Type[OutputT]) -> OutputT:
        self.calls += 1
        return self.responses.pop(0)  # type: ignore[return-value]


def response() -> CrossValidationAssessmentResponse:
    return CrossValidationAssessmentResponse(assessments=[CrossValidationAssessmentResponseItem(event_index=0, confidence=80, reasons=["Compared."], evidence=[CrossValidationEvidenceResponseItem(evidence_index=0, relation="supports", matched_claims=["Match"], conflicting_claims=[])])])


def validator(responses: List[CrossValidationAssessmentResponse]) -> tuple[LLMEventCrossValidator, FakeLLM]:
    llm = FakeLLM(responses)
    return LLMEventCrossValidator(llm, DefaultCrossValidationAssessmentParser(), FakePromptBuilder(), DefaultCrossValidationPolicy(), BatchCrossValidationConfig(max_candidates_per_batch=1)), llm


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_validator_skips_llm_for_no_related_articles() -> None:
    subject, llm = validator([])
    result = await subject.validate((candidate(()),))
    assert llm.calls == 0
    assert result[0].status.value == "insufficient_evidence"


@pytest.mark.anyio
async def test_validator_batches_and_uses_policy_result() -> None:
    first = candidate((article("a", "Reuters"),))
    second = candidate((article("b", "Bloomberg"),))
    second = second.model_copy(update={"candidate_id": "source:1", "decision": second.decision.model_copy(update={"event": second.decision.event.model_copy(update={"title": "Second"})})})
    subject, llm = validator([response(), response()])
    result = await subject.validate((first, second))
    assert llm.calls == 2
    assert len(result) == 2


@pytest.mark.anyio
async def test_validator_continues_after_first_batch_failure() -> None:
    first = candidate((article("a", "Reuters"),))
    second = candidate((article("b", "Bloomberg"),)).model_copy(update={"candidate_id": "source:1"})
    subject, llm = validator([response()])
    original = llm.generate
    calls = 0
    async def generate(messages: List[ChatMessage], response_model: Type[OutputT]) -> OutputT:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise StructuredOutputCallError(provider="test", error_type="APIError")
        return await original(messages, response_model)
    llm.generate = generate  # type: ignore[method-assign]
    result = await subject.validate((first, second))
    assert len(result) == 1


@pytest.mark.anyio
async def test_validator_raises_when_all_targets_fail() -> None:
    subject, llm = validator([])
    async def generate(messages: List[ChatMessage], response_model: Type[OutputT]) -> OutputT:
        raise StructuredOutputCallError(provider="test", error_type="APIError")
    llm.generate = generate  # type: ignore[method-assign]
    with pytest.raises(NoValidCrossValidationResultsError):
        await subject.validate((candidate((article("a", "Reuters"),)),))
