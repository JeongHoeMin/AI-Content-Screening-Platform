from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from app.evaluators import DefaultPostEvaluationParser
from app.llms import ChatResponse
from app.models import CommunityType, Post, PostEvaluationResult


def build_post(post_id: str) -> Post:
    return Post(
        id=post_id,
        source=CommunityType.REDDIT,
        title=f"Title {post_id}",
        content=f"Content {post_id}",
        author="tester",
        created_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url=f"https://example.com/posts/{post_id}",
    )


def build_item(post_id: str, score: int = 90) -> Dict[str, Any]:
    return {
        "post_id": post_id,
        "score": score,
        "is_candidate": True,
        "reasons": [f"Reason for {post_id}"],
    }


def build_response(items: List[Dict[str, Any]]) -> ChatResponse:
    content: str = json.dumps({"posts": items})
    return ChatResponse(content=content)


def test_parser_assembles_results_in_input_order() -> None:
    first_post: Post = build_post("first")
    second_post: Post = build_post("second")
    parser: DefaultPostEvaluationParser = DefaultPostEvaluationParser()
    response: ChatResponse = build_response(
        [
            build_item("second", score=82),
            build_item("first", score=91),
        ]
    )

    result: PostEvaluationResult = parser.parse(response, [first_post, second_post])

    assert [screening.post.id for screening in result.posts] == ["first", "second"]
    assert [screening.score for screening in result.posts] == [91, 82]
    assert all(screening.is_candidate for screening in result.posts)


def test_parser_propagates_invalid_json() -> None:
    parser: DefaultPostEvaluationParser = DefaultPostEvaluationParser()

    with pytest.raises(json.JSONDecodeError):
        parser.parse(ChatResponse(content="not json"), [build_post("post")])


def test_parser_propagates_invalid_response_shape() -> None:
    parser: DefaultPostEvaluationParser = DefaultPostEvaluationParser()
    response: ChatResponse = ChatResponse(content=json.dumps({"posts": [{}]}))

    with pytest.raises(ValidationError):
        parser.parse(response, [build_post("post")])


def test_parser_rejects_duplicate_input_ids() -> None:
    parser: DefaultPostEvaluationParser = DefaultPostEvaluationParser()
    duplicate_posts: List[Post] = [build_post("post"), build_post("post")]
    response: ChatResponse = build_response([build_item("post")])

    with pytest.raises(ValueError, match="duplicate IDs"):
        parser.parse(response, duplicate_posts)


def test_parser_rejects_duplicate_response_ids() -> None:
    parser: DefaultPostEvaluationParser = DefaultPostEvaluationParser()
    response: ChatResponse = build_response([build_item("post"), build_item("post")])

    with pytest.raises(ValueError, match="duplicate post IDs"):
        parser.parse(response, [build_post("post")])


def test_parser_rejects_missing_response_ids() -> None:
    parser: DefaultPostEvaluationParser = DefaultPostEvaluationParser()
    response: ChatResponse = build_response([build_item("first")])

    with pytest.raises(ValueError, match="do not match"):
        parser.parse(response, [build_post("first"), build_post("second")])


def test_parser_rejects_unknown_response_ids() -> None:
    parser: DefaultPostEvaluationParser = DefaultPostEvaluationParser()
    response: ChatResponse = build_response([build_item("unknown")])

    with pytest.raises(ValueError, match="do not match"):
        parser.parse(response, [build_post("post")])
