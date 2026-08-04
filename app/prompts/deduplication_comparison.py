from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from app.deduplicators.event_candidates import EventComparisonCandidate
from app.llms.models import ChatMessage, ChatRole
from app.prompt_templates.deduplication_comparison import (
    build_deduplication_comparison_system_prompt,
    build_deduplication_comparison_user_prompt,
)
from app.prompts.base import PromptBuilder


@dataclass(frozen=True)
class DeduplicationComparisonPromptInput:
    candidates: Tuple[EventComparisonCandidate, ...]


class DeduplicationComparisonPromptBuilder(
    PromptBuilder[DeduplicationComparisonPromptInput]
):
    """Assemble a comparison prompt without embedding template text in a service."""

    def build(
        self,
        prompt_input: DeduplicationComparisonPromptInput,
    ) -> List[ChatMessage]:
        return [
            ChatMessage(
                role=ChatRole.SYSTEM,
                content=build_deduplication_comparison_system_prompt(),
            ),
            ChatMessage(
                role=ChatRole.USER,
                content=build_deduplication_comparison_user_prompt(prompt_input.candidates),
            ),
        ]
