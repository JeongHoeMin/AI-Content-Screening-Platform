from __future__ import annotations

from typing import List, Tuple, Type, TypeVar

import pytest
from pydantic import BaseModel

from app.cross_validators import DefaultCrossValidationAssessmentParser, DefaultCrossValidationPolicy, LLMCrossValidator
from app.llms import ChatMessage, ChatRole, StructuredOutputLLM
from app.models import BatchCrossValidationConfig, CrossValidationCandidate
from app.prompts import BatchCrossValidationPromptInput, PromptBuilder
from tests.test_cross_validation_policy import candidate

OutputT = TypeVar("OutputT", bound=BaseModel)


class FakePromptBuilder(PromptBuilder[BatchCrossValidationPromptInput]):
    def build(self, prompt_input: BatchCrossValidationPromptInput) -> List[ChatMessage]:
        return [ChatMessage(role=ChatRole.USER, content="prompt")]


class FakeLLM(StructuredOutputLLM):
    def __init__(self) -> None:
        self.calls: int = 0

    async def generate(self, messages: List[ChatMessage], response_model: Type[OutputT]) -> OutputT:
        self.calls += 1
        raise AssertionError("LLM must not be called")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_validator_skips_llm_and_returns_insufficient_evidence_without_related_articles() -> None:
    llm: FakeLLM = FakeLLM()
    validator: LLMCrossValidator = LLMCrossValidator(
        structured_llm=llm,
        parser=DefaultCrossValidationAssessmentParser(),
        prompt_builder=FakePromptBuilder(),
        policy=DefaultCrossValidationPolicy(),
        config=BatchCrossValidationConfig(),
    )
    result = await validator.validate((candidate(()),))
    assert llm.calls == 0
    assert len(result) == 1
    assert result[0].confidence == 0
    assert result[0].status.value == "insufficient_evidence"
