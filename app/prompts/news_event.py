from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.llms.models import ChatMessage, ChatRole
from app.models.article import ArticleEvaluationResult
from app.prompt_templates.news_event import (
    build_news_event_system_prompt,
    build_news_event_user_prompt,
)
from app.prompts.base import PromptBuilder


@dataclass(frozen=True)
class NewsEventPromptInput:
    """Immutable input used only to build news event extraction prompts."""

    evaluation: ArticleEvaluationResult


class NewsEventPromptBuilder(PromptBuilder[NewsEventPromptInput]):
    """Builds messages for fact-only news event extraction."""

    def build(self, prompt_input: NewsEventPromptInput) -> List[ChatMessage]:
        system_content: str = build_news_event_system_prompt()
        user_content: str = build_news_event_user_prompt(prompt_input.evaluation)
        return [
            ChatMessage(role=ChatRole.SYSTEM, content=system_content),
            ChatMessage(role=ChatRole.USER, content=user_content),
        ]
