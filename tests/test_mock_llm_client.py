from __future__ import annotations

from typing import List

import pytest

from app.llms import ChatMessage, ChatResponse, ChatRole, GenerationConfig
from app.llms.base import LLMClient
from app.llms.mock import MockLLMClient


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_chat_role_values() -> None:
    assert ChatRole.SYSTEM.value == "system"
    assert ChatRole.USER.value == "user"
    assert ChatRole.ASSISTANT.value == "assistant"


def test_chat_message_stores_role_and_content() -> None:
    message: ChatMessage = ChatMessage(role=ChatRole.USER, content="Hello")

    assert message.role == ChatRole.USER
    assert message.content == "Hello"


def test_generation_config_defaults_and_values() -> None:
    default_config: GenerationConfig = GenerationConfig()
    custom_config: GenerationConfig = GenerationConfig(
        temperature=0.7,
        max_tokens=500,
    )

    assert default_config.temperature is None
    assert default_config.max_tokens is None
    assert custom_config.temperature == 0.7
    assert custom_config.max_tokens == 500
    assert not hasattr(custom_config, "model")


def test_chat_response_defaults_raw_to_none() -> None:
    response: ChatResponse = ChatResponse(content="Mock Response")

    assert response.content == "Mock Response"


@pytest.mark.anyio
async def test_mock_llm_client_returns_chat_response() -> None:
    client: LLMClient = MockLLMClient()
    messages: List[ChatMessage] = [
        ChatMessage(role=ChatRole.USER, content="Hello"),
    ]

    response: ChatResponse = await client.chat(messages)

    assert isinstance(response, ChatResponse)
    assert response.content == "Mock Response"


@pytest.mark.anyio
async def test_mock_llm_client_accepts_optional_generation_config() -> None:
    client: MockLLMClient = MockLLMClient()
    messages: List[ChatMessage] = [
        ChatMessage(role=ChatRole.USER, content="Hello"),
    ]

    response_without_config: ChatResponse = await client.chat(messages, config=None)
    response_with_config: ChatResponse = await client.chat(
        messages,
        config=GenerationConfig(),
    )

    assert response_without_config == response_with_config


@pytest.mark.anyio
async def test_mock_llm_client_is_stateless() -> None:
    client: MockLLMClient = MockLLMClient()
    messages: List[ChatMessage] = [
        ChatMessage(role=ChatRole.USER, content="Hello"),
    ]

    first_response: ChatResponse = await client.chat(messages)
    second_response: ChatResponse = await client.chat(messages)

    assert first_response == second_response
