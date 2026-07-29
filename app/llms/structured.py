from __future__ import annotations

from typing import List, Protocol, Type, TypeVar

from pydantic import BaseModel

from app.llms.base import LLMClient
from app.llms.models import ChatMessage, ChatResponse

OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredOutputLLM(Protocol):
    """Generates validated typed structured output from prepared messages.

    Implementations call an LLM, validate raw provider content with the supplied
    response_model, and return only the validated typed object. They never
    return raw JSON, raw chat completions, or provider SDK responses.

    Implementations neither build prompts, manage prompt templates, split
    batches, retry requests, map output to NewsEvent values, validate
    event-to-article relationships, nor modify workflow state.
    """

    async def generate(
        self,
        messages: List[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        """Return only one response validated as the requested Pydantic model."""
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
