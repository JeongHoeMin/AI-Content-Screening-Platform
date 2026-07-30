from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.llms.budget import (
    BudgetedStructuredOutputLLM,
    ProviderRequestBudget,
    ProviderRequestBudgetExceededError,
)
from app.llms.models import ChatMessage, ChatRole


class Output(BaseModel):
    value: str


class FakeStructuredOutputLLM:
    def __init__(self) -> None:
        self.calls: int = 0

    async def generate(self, messages: list[ChatMessage], response_model: type[Output]) -> Output:
        self.calls += 1
        return Output(value="ok")


@pytest.mark.anyio
async def test_budgeted_llm_blocks_provider_call_after_execution_limit() -> None:
    delegate: FakeStructuredOutputLLM = FakeStructuredOutputLLM()
    budget: ProviderRequestBudget = ProviderRequestBudget(max_requests=1)
    llm: BudgetedStructuredOutputLLM = BudgetedStructuredOutputLLM(delegate, budget)
    messages: list[ChatMessage] = [ChatMessage(role=ChatRole.USER, content="safe")]

    with budget.execution_scope():
        assert await llm.generate(messages, Output) == Output(value="ok")
        with pytest.raises(ProviderRequestBudgetExceededError):
            await llm.generate(messages, Output)

    assert delegate.calls == 1


@pytest.mark.anyio
async def test_budget_scope_resets_for_each_execution() -> None:
    budget: ProviderRequestBudget = ProviderRequestBudget(max_requests=1)

    with budget.execution_scope():
        budget.claim()
    with budget.execution_scope():
        budget.claim()
