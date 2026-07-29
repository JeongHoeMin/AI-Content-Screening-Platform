from __future__ import annotations

from typing import Any, Optional, Protocol, Type, TypeVar

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel

from app.llms.models import ChatMessage, ChatRole
from app.llms.structured import StructuredOutputLLM

OutputT = TypeVar("OutputT", bound=BaseModel)


class StructuredOutputCallError(RuntimeError):
    """Raised when an OpenAI SDK request fails before a usable response exists."""

    def __init__(self, error_type: str) -> None:
        self.error_type: str = error_type
        super().__init__(f"OpenAI structured output request failed: {error_type}")


class StructuredOutputResponseError(ValueError):
    """Raised when an OpenAI response cannot provide a complete parsed result."""

    def __init__(self, reason: str) -> None:
        self.reason: str = reason
        super().__init__(f"OpenAI structured output failed: {reason}")


class StructuredOutputClient(Protocol):
    """Provider boundary that returns parsed Pydantic results only."""

    async def parse(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[OutputT],
    ) -> OutputT:
        """Return a completed and parsed structured output response."""
        ...


class OpenAIResponsesStructuredOutputClient(StructuredOutputClient):
    """OpenAI Responses API adapter isolated from extraction orchestration."""

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client: AsyncOpenAI = client

    async def parse(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[OutputT],
    ) -> OutputT:
        try:
            response: Any = await self._client.responses.parse(
                model=model,
                instructions=system_prompt,
                input=user_prompt,
                text_format=response_model,
            )
        except OpenAIError as error:
            raise StructuredOutputCallError(type(error).__name__) from error
        status: Optional[str] = getattr(response, "status", None)
        if status == "failed":
            raise StructuredOutputResponseError("response_failed")
        if status == "incomplete":
            raise StructuredOutputResponseError("response_incomplete")
        if status != "completed":
            raise StructuredOutputResponseError(
                f"unknown_response_status:{status or 'none'}"
            )
        parsed: Optional[OutputT] = getattr(response, "output_parsed", None)
        if parsed is None:
            if self._contains_refusal(response):
                raise StructuredOutputResponseError("refusal")
            raise StructuredOutputResponseError("missing_parsed_output")
        return parsed

    @staticmethod
    def _contains_refusal(response: Any) -> bool:
        for output_item in getattr(response, "output", ()):
            for content_item in getattr(output_item, "content", ()):
                if getattr(content_item, "type", None) == "refusal":
                    return True
        return False


class OpenAIResponsesStructuredOutputLLM(StructuredOutputLLM):
    """Adapts prepared chat messages to the OpenAI Responses structured boundary."""

    def __init__(self, client: StructuredOutputClient, model: str) -> None:
        self._client: StructuredOutputClient = client
        self._model: str = model

    async def generate(
        self,
        messages: list[ChatMessage],
        response_model: Type[OutputT],
    ) -> OutputT:
        system_prompt: str = "\n\n".join(
            message.content for message in messages if message.role is ChatRole.SYSTEM
        )
        user_prompt: str = "\n\n".join(
            message.content for message in messages if message.role is not ChatRole.SYSTEM
        )
        return await self._client.parse(
            model=self._model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
        )
