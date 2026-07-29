from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from app.llms.models import ChatMessage, ChatRole
from app.models.cross_validation import CrossValidationCandidate
from app.prompt_templates.cross_validation import (
    build_cross_validation_system_prompt,
    build_cross_validation_user_prompt,
)
from app.prompts.base import PromptBuilder


@dataclass(frozen=True)
class BatchCrossValidationPromptInput:
    candidates: Tuple[CrossValidationCandidate, ...]


class CrossValidationPromptBuilder(PromptBuilder[BatchCrossValidationPromptInput]):
    def build(self, prompt_input: BatchCrossValidationPromptInput) -> List[ChatMessage]:
        return [
            ChatMessage(role=ChatRole.SYSTEM, content=build_cross_validation_system_prompt()),
            ChatMessage(role=ChatRole.USER, content=build_cross_validation_user_prompt(prompt_input.candidates)),
        ]
