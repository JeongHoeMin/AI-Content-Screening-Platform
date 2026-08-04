from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import List, Tuple

import pytest

from app.llms import ChatMessage, ChatRole
from app.models import Article
from app.models.article import ArticleParagraph
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
    assert "event_type" in prompt
    assert "event_facts" in prompt
    assert "major_supply_contract" in prompt
    assert "bankruptcy and major_supply_contract require financial_event" in prompt
    assert 'source "dart"' in prompt
    assert "단일판매ㆍ공급계약체결" in prompt


def test_user_prompt_separates_article_fields_as_data() -> None:
    prompt: str = build_news_event_user_prompt(build_articles())

    assert "<article-data>" in prompt
    assert 'Article ID: "article-1"' in prompt
    assert 'Source: "Example News"' in prompt
    assert 'Title: "Samsung expands HBM production"' in prompt


def test_user_prompt_numbers_article_evidence_paragraphs() -> None:
    article: Article = build_articles()[0].model_copy(
        update={"paragraphs": (ArticleParagraph(index=1, content="Evidence paragraph."),)}
    )

    prompt: str = build_news_event_user_prompt((article,))

    assert "Paragraph 1: \"Evidence paragraph.\"" in prompt
