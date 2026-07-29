from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from app.llms.models import ChatMessage, ChatRole
from app.models.article import Article
from app.prompt_templates.news_event import (
    build_news_event_system_prompt,
    build_news_event_user_prompt,
)
from app.prompts.base import PromptBuilder


@dataclass(frozen=True)
class BatchNewsEventPromptInput:
    """Immutable input used only to build batch extraction prompts."""

    articles: Tuple[Article, ...]


class NewsEventPromptBuilder(PromptBuilder[BatchNewsEventPromptInput]):
    """Builds messages for fact-only batch news event extraction."""

    def build(self, prompt_input: BatchNewsEventPromptInput) -> List[ChatMessage]:
        system_content: str = build_news_event_system_prompt()
        user_content: str = build_news_event_user_prompt(prompt_input.articles)
        return [
            ChatMessage(role=ChatRole.SYSTEM, content=system_content),
            ChatMessage(role=ChatRole.USER, content=user_content),
        ]
