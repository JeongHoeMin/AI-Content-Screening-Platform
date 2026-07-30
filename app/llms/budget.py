from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterator, Optional, Type, TypeVar

from pydantic import BaseModel

from app.llms.models import ChatMessage
from app.llms.structured import StructuredOutputLLM

OutputT = TypeVar("OutputT", bound=BaseModel)


class ProviderRequestBudgetExceededError(RuntimeError):
    """Raised before a provider call would exceed the execution request cap."""


@dataclass
class _BudgetState:
    used_requests: int = 0


class ProviderRequestBudget:
    """Context-local provider request cap shared by one workflow execution."""

    def __init__(self, max_requests: int) -> None:
        if max_requests <= 0:
            raise ValueError("Provider request budget must be positive")
        self._max_requests: int = max_requests
        self._state: ContextVar[Optional[_BudgetState]] = ContextVar(
            "provider_request_budget_state", default=None
        )

    @contextmanager
    def execution_scope(self) -> Iterator[None]:
        token: Token[Optional[_BudgetState]] = self._state.set(_BudgetState())
        try:
            yield
        finally:
            self._state.reset(token)

    def claim(self) -> None:
        state: Optional[_BudgetState] = self._state.get()
        if state is None:
            raise RuntimeError("Provider request budget requires an execution scope")
        if state.used_requests >= self._max_requests:
            raise ProviderRequestBudgetExceededError("Provider request budget exceeded")
        state.used_requests += 1


class BudgetedStructuredOutputLLM(StructuredOutputLLM):
    """Claim a request budget slot before delegating one structured provider call."""

    def __init__(self, delegate: StructuredOutputLLM, budget: ProviderRequestBudget) -> None:
        self._delegate: StructuredOutputLLM = delegate
        self._budget: ProviderRequestBudget = budget

    async def generate(
        self,
        messages: list[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        self._budget.claim()
        return await self._delegate.generate(messages, response_model)
