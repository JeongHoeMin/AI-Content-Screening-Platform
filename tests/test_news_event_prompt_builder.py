from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import List, Tuple

import pytest

from app.llms import ChatMessage, ChatRole
from app.models import Article
from app.prompt_templates import (
    build_news_event_system_prompt,
    build_news_event_user_prompt,
)
from app.prompts import BatchNewsEventPromptInput, NewsEventPromptBuilder


def build_articles() -> Tuple[Article, ...]:
    return (
        Article(
            id="article-1",
            title="Samsung expands HBM production",
            content="Samsung announced an expansion." * 20,
            source="Example News",
            published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
            url="https://example.com/articles/1",
        ),
    )


def test_batch_prompt_input_is_immutable() -> None:
    prompt_input: BatchNewsEventPromptInput = BatchNewsEventPromptInput(
        articles=build_articles()
    )

    with pytest.raises(FrozenInstanceError):
        prompt_input.articles = ()


def test_prompt_builder_returns_batch_messages() -> None:
    articles: Tuple[Article, ...] = build_articles()
    builder: NewsEventPromptBuilder = NewsEventPromptBuilder()

    messages: List[ChatMessage] = builder.build(
        BatchNewsEventPromptInput(articles=articles)
    )

    assert [message.role for message in messages] == [ChatRole.SYSTEM, ChatRole.USER]
    assert messages[0].content == build_news_event_system_prompt()
    assert messages[1].content == build_news_event_user_prompt(articles)


def test_system_prompt_defines_extraction_boundary_and_rationale_contract() -> None:
    prompt: str = build_news_event_system_prompt()

    assert "untrusted data" in prompt
    assert "chain-of-thought" in prompt
    assert "ticker" in prompt


def test_user_prompt_separates_article_fields_as_data() -> None:
    prompt: str = build_news_event_user_prompt(build_articles())

    assert "<article-data>" in prompt
    assert 'Article ID: "article-1"' in prompt
    assert 'Source: "Example News"' in prompt
    assert 'Title: "Samsung expands HBM production"' in prompt
