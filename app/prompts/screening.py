from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from app.llms.models import ChatMessage, ChatRole
from app.models.screening import ScreeningCandidate
from app.prompt_templates.screening import (
    build_screening_system_prompt,
    build_screening_user_prompt,
)
from app.prompts.base import PromptBuilder


@dataclass(frozen=True)
class BatchScreeningPromptInput:
    """Immutable input used only to build batch event screening prompts."""

    candidates: Tuple[ScreeningCandidate, ...]


class ScreeningPromptBuilder(PromptBuilder[BatchScreeningPromptInput]):
    """Builds messages for structured event assessment without deciding actions."""

    def build(self, prompt_input: BatchScreeningPromptInput) -> List[ChatMessage]:
        system_content: str = build_screening_system_prompt()
        user_content: str = build_screening_user_prompt(prompt_input.candidates)
        return [
            ChatMessage(role=ChatRole.SYSTEM, content=system_content),
            ChatMessage(role=ChatRole.USER, content=user_content),
        ]
