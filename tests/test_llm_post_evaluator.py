from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

import pytest

from app.evaluators import (
    LLMPostEvaluator,
    PostEvaluationParser,
    PostEvaluationRequester,
)
from app.llms import ChatResponse
from app.models import CommunityType, Post, PostEvaluationResult


class FakeRequester(PostEvaluationRequester):
    def __init__(
        self,
        response: ChatResponse,
        error: Optional[Exception] = None,
    ) -> None:
        self.response: ChatResponse = response
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.received_posts: Optional[Sequence[Post]] = None

    async def request(self, posts: Sequence[Post]) -> ChatResponse:
        self.calls += 1
        self.received_posts = posts
        if self.error is not None:
            raise self.error
        return self.response


class FakeParser(PostEvaluationParser):
    def __init__(
        self,
        result: PostEvaluationResult,
        error: Optional[Exception] = None,
    ) -> None:
        self.result: PostEvaluationResult = result
        self.error: Optional[Exception] = error
        self.calls: int = 0
        self.received_response: Optional[ChatResponse] = None
        self.received_posts: Optional[Sequence[Post]] = None

    def parse(
        self,
        response: ChatResponse,
        posts: Sequence[Post],
    ) -> PostEvaluationResult:
        self.calls += 1
        self.received_response = response
        self.received_posts = posts
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def build_post() -> Post:
    return Post(
        id="evaluator-post",
        source=CommunityType.REDDIT,
        title="Evaluator post",
        content="Evaluator content",
        author="tester",
        created_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url="https://example.com/posts/evaluator-post",
    )


@pytest.mark.anyio
async def test_llm_post_evaluator_orchestrates_request_and_parsing() -> None:
    posts: List[Post] = [build_post()]
    response: ChatResponse = ChatResponse(content="raw response")
    expected_result: PostEvaluationResult = PostEvaluationResult(posts=[])
    requester: FakeRequester = FakeRequester(response)
    parser: FakeParser = FakeParser(expected_result)
    evaluator: LLMPostEvaluator = LLMPostEvaluator(requester=requester, parser=parser)

    result: PostEvaluationResult = await evaluator.evaluate(posts)

    assert requester.calls == 1
    assert requester.received_posts is posts
    assert parser.calls == 1
    assert parser.received_response is response
    assert parser.received_posts is posts
    assert result is expected_result


@pytest.mark.anyio
async def test_llm_post_evaluator_propagates_requester_errors() -> None:
    expected_error: RuntimeError = RuntimeError("request failed")
    requester: FakeRequester = FakeRequester(
        response=ChatResponse(content="unused"),
        error=expected_error,
    )
    parser: FakeParser = FakeParser(PostEvaluationResult(posts=[]))
    evaluator: LLMPostEvaluator = LLMPostEvaluator(requester=requester, parser=parser)

    with pytest.raises(RuntimeError) as error_info:
        await evaluator.evaluate([build_post()])

    assert error_info.value is expected_error
    assert parser.calls == 0


@pytest.mark.anyio
async def test_llm_post_evaluator_propagates_parser_errors() -> None:
    expected_error: ValueError = ValueError("parse failed")
    requester: FakeRequester = FakeRequester(ChatResponse(content="raw response"))
    parser: FakeParser = FakeParser(
        result=PostEvaluationResult(posts=[]),
        error=expected_error,
    )
    evaluator: LLMPostEvaluator = LLMPostEvaluator(requester=requester, parser=parser)

    with pytest.raises(ValueError) as error_info:
        await evaluator.evaluate([build_post()])

    assert error_info.value is expected_error
    assert requester.calls == 1
    assert parser.calls == 1
