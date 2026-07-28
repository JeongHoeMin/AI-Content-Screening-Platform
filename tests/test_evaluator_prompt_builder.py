from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import List, Sequence

import pytest

from app.llms import ChatMessage, ChatRole
from app.models import CommunityType, Post
from app.prompt_templates import (
    build_evaluator_system_prompt,
    build_evaluator_user_prompt,
)
from app.prompts import EvaluatorPromptBuilder, EvaluatorPromptInput, PromptBuilder


def build_post() -> Post:
    return Post(
        id="prompt-post",
        source=CommunityType.REDDIT,
        title="테스트 제목",
        content="테스트 본문",
        author="tester",
        created_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url="https://example.com/posts/prompt-post",
        view_count=10,
        like_count=3,
        comment_count=2,
    )


def test_evaluator_prompt_input_is_immutable() -> None:
    post: Post = build_post()
    prompt_input: EvaluatorPromptInput = EvaluatorPromptInput(posts=[post])

    with pytest.raises(FrozenInstanceError):
        prompt_input.posts = []  # type: ignore[misc]


def test_evaluator_prompt_input_accepts_read_only_post_sequence() -> None:
    posts: Sequence[Post] = (build_post(),)
    prompt_input: EvaluatorPromptInput = EvaluatorPromptInput(posts=posts)

    assert prompt_input.posts == posts


def test_evaluator_prompt_builder_uses_generic_prompt_builder_contract() -> None:
    builder: PromptBuilder[EvaluatorPromptInput] = EvaluatorPromptBuilder()
    prompt_input: EvaluatorPromptInput = EvaluatorPromptInput(posts=[build_post()])

    messages: List[ChatMessage] = builder.build(prompt_input)

    assert len(messages) == 2


def test_evaluator_prompt_builder_uses_template_messages_in_order() -> None:
    post: Post = build_post()
    prompt_input: EvaluatorPromptInput = EvaluatorPromptInput(posts=[post])
    builder: EvaluatorPromptBuilder = EvaluatorPromptBuilder()

    messages: List[ChatMessage] = builder.build(prompt_input)

    assert [message.role for message in messages] == [ChatRole.SYSTEM, ChatRole.USER]
    assert messages[0].content == build_evaluator_system_prompt()
    assert messages[1].content == build_evaluator_user_prompt([post])


def test_evaluator_user_template_serializes_post_data() -> None:
    prompt: str = build_evaluator_user_prompt([build_post()])

    assert "테스트 제목" in prompt
    assert "테스트 본문" in prompt
    assert '"like_count": 3' in prompt


def test_evaluator_user_template_represents_empty_posts_as_json_array() -> None:
    prompt: str = build_evaluator_user_prompt([])

    assert prompt.endswith("[]")
