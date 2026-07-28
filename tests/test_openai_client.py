from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from app.llms import (
    ChatMessage,
    ChatResponse,
    ChatRole,
    GenerationConfig,
    LLMClient,
    OpenAIClient,
)


@dataclass
class FakeMessage:
    content: Optional[str]


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeResponse:
    choices: List[FakeChoice]


class FakeCompletions:
    def __init__(
        self,
        response: FakeResponse,
        error: Optional[Exception] = None,
    ) -> None:
        self._response: FakeResponse = response
        self._error: Optional[Exception] = error
        self.request_options: Optional[Dict[str, Any]] = None

    async def create(self, **request_options: Any) -> FakeResponse:
        self.request_options = request_options
        if self._error is not None:
            raise self._error
        return self._response


class FakeChat:
    def __init__(self, completions: FakeCompletions) -> None:
        self.completions: FakeCompletions = completions


class FakeAsyncOpenAI:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat: FakeChat = FakeChat(completions)


def build_client(
    content: Optional[str] = "OpenAI response",
    error: Optional[Exception] = None,
) -> tuple[OpenAIClient, FakeCompletions]:
    response: FakeResponse = FakeResponse(
        choices=[FakeChoice(message=FakeMessage(content=content))],
    )
    completions: FakeCompletions = FakeCompletions(response=response, error=error)
    sdk_client: FakeAsyncOpenAI = FakeAsyncOpenAI(completions)
    client: OpenAIClient = OpenAIClient(client=sdk_client, model="test-model")  # type: ignore[arg-type]
    return client, completions


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_openai_client_maps_messages_and_generation_config() -> None:
    client: OpenAIClient
    completions: FakeCompletions
    client, completions = build_client()
    messages: List[ChatMessage] = [
        ChatMessage(role=ChatRole.SYSTEM, content="System instruction"),
        ChatMessage(role=ChatRole.USER, content="User request"),
        ChatMessage(role=ChatRole.ASSISTANT, content="Assistant answer"),
    ]
    config: GenerationConfig = GenerationConfig(temperature=0.4, max_tokens=256)

    response: ChatResponse = await client.chat(messages, config=config)

    assert response.content == "OpenAI response"
    assert completions.request_options == {
        "model": "test-model",
        "messages": [
            {"role": "system", "content": "System instruction"},
            {"role": "user", "content": "User request"},
            {"role": "assistant", "content": "Assistant answer"},
        ],
        "temperature": 0.4,
        "max_tokens": 256,
    }


@pytest.mark.anyio
async def test_openai_client_omits_optional_config_when_none() -> None:
    client: OpenAIClient
    completions: FakeCompletions
    client, completions = build_client()
    messages: List[ChatMessage] = [
        ChatMessage(role=ChatRole.USER, content="Hello"),
    ]

    response: ChatResponse = await client.chat(messages, config=None)

    assert response.content == "OpenAI response"
    assert completions.request_options == {
        "model": "test-model",
        "messages": [{"role": "user", "content": "Hello"}],
    }


@pytest.mark.anyio
async def test_openai_client_returns_empty_content_for_empty_sdk_message() -> None:
    client: OpenAIClient
    completions: FakeCompletions
    client, completions = build_client(content=None)

    response: ChatResponse = await client.chat([])

    assert response.content == ""
    assert completions.request_options is not None


@pytest.mark.anyio
async def test_openai_client_implements_llm_client_protocol() -> None:
    client: OpenAIClient
    completions: FakeCompletions
    client, completions = build_client()
    llm: LLMClient = client

    response: ChatResponse = await llm.chat([])

    assert response.content == "OpenAI response"
    assert completions.request_options is not None


@pytest.mark.anyio
async def test_openai_client_propagates_sdk_errors() -> None:
    expected_error: RuntimeError = RuntimeError("SDK failed")
    client: OpenAIClient
    _completions: FakeCompletions
    client, _completions = build_client(error=expected_error)

    with pytest.raises(RuntimeError) as error_info:
        await client.chat([])

    assert error_info.value is expected_error
