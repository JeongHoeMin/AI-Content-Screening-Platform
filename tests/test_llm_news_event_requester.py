from __future__ import annotations

from typing import List, Optional

import pytest

from app.extractors import LLMNewsEventRequester, NewsEventRequester
from app.llms import ChatMessage, ChatResponse, ChatRole, GenerationConfig, LLMClient


class FakeLLMClient(LLMClient):
    def __init__(
        self,
        response: ChatResponse,
        error: Optional[Exception] = None,
    ) -> None:
        self.response: ChatResponse = response
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.received_messages: Optional[List[ChatMessage]] = None
        self.received_config: Optional[GenerationConfig] = None

    async def chat(
        self,
        messages: List[ChatMessage],
        config: Optional[GenerationConfig] = None,
    ) -> ChatResponse:
        self.calls += 1
        self.received_messages = messages
        self.received_config = config
        if self.error is not None:
            raise self.error
        return self.response


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def build_messages() -> List[ChatMessage]:
    return [ChatMessage(role=ChatRole.USER, content="Extract news events")]


def test_requester_constructor_stores_client_without_calling_it() -> None:
    llm_client: FakeLLMClient = FakeLLMClient(ChatResponse(content="unused"))

    requester: LLMNewsEventRequester = LLMNewsEventRequester(llm_client)

    assert requester._llm_client is llm_client
    assert llm_client.calls == 0


@pytest.mark.anyio
async def test_requester_forwards_messages_and_response_without_copying() -> None:
    messages: List[ChatMessage] = build_messages()
    expected_response: ChatResponse = ChatResponse(content='{"events":[]}')
    llm_client: FakeLLMClient = FakeLLMClient(expected_response)
    requester: NewsEventRequester = LLMNewsEventRequester(llm_client)

    response: ChatResponse = await requester.request(messages)

    assert llm_client.calls == 1
    assert llm_client.received_messages is messages
    assert llm_client.received_config is None
    assert response is expected_response


@pytest.mark.anyio
async def test_requester_propagates_llm_client_error_without_wrapping() -> None:
    expected_error: RuntimeError = RuntimeError("LLM request failed")
    llm_client: FakeLLMClient = FakeLLMClient(
        response=ChatResponse(content="unused"),
        error=expected_error,
    )
    requester: LLMNewsEventRequester = LLMNewsEventRequester(llm_client)

    with pytest.raises(RuntimeError) as error_info:
        await requester.request(build_messages())

    assert error_info.value is expected_error
    assert llm_client.calls == 1
