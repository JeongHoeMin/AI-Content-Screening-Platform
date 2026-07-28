from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from app.llms.models import ChatMessage, ChatRole
from app.models.post import Post
from app.prompt_templates.evaluator import (
    build_evaluator_system_prompt,
    build_evaluator_user_prompt,
)
from app.prompts.base import PromptBuilder


@dataclass(frozen=True)
class EvaluatorPromptInput:
    """Validated data passed to the evaluator prompt builder."""

    posts: Sequence[Post]


class EvaluatorPromptBuilder(PromptBuilder[EvaluatorPromptInput]):
    """Builds chat messages for post evaluation."""

    def build(self, prompt_input: EvaluatorPromptInput) -> List[ChatMessage]:
        system_content: str = build_evaluator_system_prompt()
        user_content: str = build_evaluator_user_prompt(prompt_input.posts)
        return [
            ChatMessage(role=ChatRole.SYSTEM, content=system_content),
            ChatMessage(role=ChatRole.USER, content=user_content),
        ]
