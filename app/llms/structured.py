from __future__ import annotations

from typing import List, Protocol, Type, TypeVar

from pydantic import BaseModel

from app.llms.base import LLMClient
from app.llms.models import ChatMessage, ChatResponse

OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredOutputLLM(Protocol):
    """Generates validated typed structured output from prepared messages.

    Implementations neither build prompts, split batches, retry requests, map
    output to domain events, nor validate event-to-article relationships.
    """

    async def generate(
        self,
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        """Return one response validated as the requested Pydantic model."""
        ...


class PydanticStructuredOutputLLM(StructuredOutputLLM):
    """Adapts the project LLMClient contract to typed Pydantic output."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client: LLMClient = llm_client

    async def generate(
        self,
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        response: ChatResponse = await self._llm_client.chat(
            messages=messages,
            config=None,
        )
        return response_model.model_validate_json(response.content)
