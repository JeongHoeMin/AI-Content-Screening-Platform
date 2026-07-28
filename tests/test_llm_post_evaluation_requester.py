from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

import pytest

from app.evaluators import LLMPostEvaluationRequester, PostEvaluationRequester
from app.llms import ChatMessage, ChatResponse, ChatRole, GenerationConfig, LLMClient
from app.models import CommunityType, Post
from app.prompts import EvaluatorPromptInput, PromptBuilder


class FakePromptBuilder(PromptBuilder[EvaluatorPromptInput]):
    def __init__(
        self,
        messages: List[ChatMessage],
        error: Optional[Exception] = None,
    ) -> None:
        self.messages: List[ChatMessage] = messages
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.received_input: Optional[EvaluatorPromptInput] = None

    def build(self, prompt_input: EvaluatorPromptInput) -> List[ChatMessage]:
        self.calls += 1
        self.received_input = prompt_input
        if self.error is not None:
            raise self.error
        return self.messages


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


def build_post() -> Post:
    return Post(
        id="requester-post",
        source=CommunityType.REDDIT,
        title="Requester post",
        content="Requester content",
        author="tester",
        created_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url="https://example.com/posts/requester-post",
    )


def build_messages() -> List[ChatMessage]:
    return [ChatMessage(role=ChatRole.USER, content="Prepared prompt")]


@pytest.mark.anyio
async def test_requester_orchestrates_prompt_and_llm_without_copying() -> None:
    posts: Sequence[Post] = (build_post(),)
    messages: List[ChatMessage] = build_messages()
    expected_response: ChatResponse = ChatResponse(content="Raw evaluation response")
    fake_builder: FakePromptBuilder = FakePromptBuilder(messages)
    fake_llm_client: FakeLLMClient = FakeLLMClient(expected_response)
    prompt_builder: PromptBuilder[EvaluatorPromptInput] = fake_builder
    llm_client: LLMClient = fake_llm_client
    requester: PostEvaluationRequester = LLMPostEvaluationRequester(
        llm_client=llm_client,
        prompt_builder=prompt_builder,
    )

    response: ChatResponse = await requester.request(posts)

    assert fake_builder.calls == 1
    assert fake_builder.received_input is not None
    assert fake_builder.received_input.posts is posts
    assert fake_llm_client.calls == 1
    assert fake_llm_client.received_messages is messages
    assert fake_llm_client.received_config is None
    assert response is expected_response


@pytest.mark.anyio
async def test_requester_propagates_prompt_builder_errors() -> None:
    expected_error: ValueError = ValueError("prompt build failed")
    prompt_builder: FakePromptBuilder = FakePromptBuilder(
        messages=build_messages(),
        error=expected_error,
    )
    llm_client: FakeLLMClient = FakeLLMClient(ChatResponse(content="unused"))
    requester: LLMPostEvaluationRequester = LLMPostEvaluationRequester(
        llm_client=llm_client,
        prompt_builder=prompt_builder,
    )

    with pytest.raises(ValueError) as error_info:
        await requester.request((build_post(),))

    assert error_info.value is expected_error
    assert llm_client.calls == 0


@pytest.mark.anyio
async def test_requester_propagates_llm_client_errors() -> None:
    expected_error: RuntimeError = RuntimeError("llm failed")
    prompt_builder: FakePromptBuilder = FakePromptBuilder(messages=build_messages())
    llm_client: FakeLLMClient = FakeLLMClient(
        response=ChatResponse(content="unused"),
        error=expected_error,
    )
    requester: LLMPostEvaluationRequester = LLMPostEvaluationRequester(
        llm_client=llm_client,
        prompt_builder=prompt_builder,
    )

    with pytest.raises(RuntimeError) as error_info:
        await requester.request((build_post(),))

    assert error_info.value is expected_error
    assert prompt_builder.calls == 1
    assert llm_client.calls == 1
