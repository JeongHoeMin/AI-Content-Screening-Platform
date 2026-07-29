from __future__ import annotations

from typing import List, Optional

import pytest
from pydantic import BaseModel

from app.llms import (
    ChatMessage,
    ChatResponse,
    ChatRole,
    GenerationConfig,
    LLMClient,
    PydanticStructuredOutputLLM,
)


class OutputModel(BaseModel):
    value: str


class FakeLLMClient(LLMClient):
    def __init__(
        self,
        response: ChatResponse,
        error: Optional[Exception] = None,
    ) -> None:
        self.response: ChatResponse = response
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.messages: Optional[List[ChatMessage]] = None
        self.config: Optional[GenerationConfig] = GenerationConfig()

    async def chat(
        self,
        messages: List[ChatMessage],
        config: Optional[GenerationConfig] = None,
    ) -> ChatResponse:
        self.calls += 1
        self.messages = messages
        self.config = config
        if self.error is not None:
            raise self.error
        return self.response


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_structured_adapter_forwards_messages_and_validates_response() -> None:
    messages: List[ChatMessage] = [
        ChatMessage(role=ChatRole.USER, content="Return structured output")
    ]
    client: FakeLLMClient = FakeLLMClient(ChatResponse(content='{"value":"ok"}'))
    llm: PydanticStructuredOutputLLM = PydanticStructuredOutputLLM(client)

    result: OutputModel = await llm.generate(messages, OutputModel)

    assert result == OutputModel(value="ok")
    assert client.messages is messages
    assert client.config is None


@pytest.mark.anyio
async def test_structured_adapter_propagates_client_error_without_wrapping() -> None:
    expected_error: RuntimeError = RuntimeError("provider failed")
    client: FakeLLMClient = FakeLLMClient(
        ChatResponse(content="unused"),
        error=expected_error,
    )
    llm: PydanticStructuredOutputLLM = PydanticStructuredOutputLLM(client)

    with pytest.raises(RuntimeError) as error_info:
        await llm.generate([], OutputModel)

    assert error_info.value is expected_error
