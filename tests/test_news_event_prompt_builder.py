from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import List

import pytest

from app.llms import ChatMessage, ChatRole
from app.models import Article, ArticleEvaluationResult
from app.prompt_templates import (
    build_news_event_system_prompt,
    build_news_event_user_prompt,
)
from app.prompts import NewsEventPromptBuilder, NewsEventPromptInput


def build_evaluation() -> ArticleEvaluationResult:
    return ArticleEvaluationResult(
        article=Article(
            id="article-1",
            title="삼성전자, HBM 생산 확대",
            content="삼성전자는 HBM 생산 확대 계획을 발표했다.",
            source="Example News",
            published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
            url="https://example.com/articles/1",
        ),
        score=95,
        is_relevant=True,
        reasons=["반도체 생산 계획"],
    )


def test_news_event_prompt_input_is_immutable() -> None:
    prompt_input: NewsEventPromptInput = NewsEventPromptInput(
        evaluation=build_evaluation()
    )

    with pytest.raises(FrozenInstanceError):
        prompt_input.evaluation = build_evaluation()


def test_prompt_builder_returns_system_and_user_messages() -> None:
    evaluation: ArticleEvaluationResult = build_evaluation()
    builder: NewsEventPromptBuilder = NewsEventPromptBuilder()

    messages: List[ChatMessage] = builder.build(
        NewsEventPromptInput(evaluation=evaluation)
    )

    assert [message.role for message in messages] == [
        ChatRole.SYSTEM,
        ChatRole.USER,
    ]
    assert messages[0].content == build_news_event_system_prompt()
    assert messages[1].content == build_news_event_user_prompt(evaluation)


def test_system_prompt_uses_strict_shared_response_contract() -> None:
    prompt: str = build_news_event_system_prompt()

    assert '"NewsEventExtractionResponse"' in prompt
    assert '"additionalProperties": false' in prompt
    assert '"events"' in prompt
    assert '"direct"' in prompt
    assert '"indirect"' in prompt
    assert "Do not recommend stocks" in prompt
    assert "Do not produce ticker, sentiment, confidence, impact" in prompt
    assert "beneficiaries, victims, or competitors" in prompt


def test_user_prompt_serializes_complete_evaluation_as_json() -> None:
    evaluation: ArticleEvaluationResult = build_evaluation()

    prompt: str = build_news_event_user_prompt(evaluation)
    serialized_evaluation: str = prompt.split("\n", maxsplit=1)[1]
    payload: object = json.loads(serialized_evaluation)

    assert isinstance(payload, dict)
    assert payload["article"]["id"] == "article-1"
    assert payload["article"]["title"] == "삼성전자, HBM 생산 확대"
    assert payload["score"] == 95
