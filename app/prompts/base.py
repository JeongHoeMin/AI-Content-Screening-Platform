from __future__ import annotations

from typing import Generic, List, Protocol, TypeVar

from app.llms.models import ChatMessage

InputT = TypeVar("InputT")


class PromptBuilder(Protocol, Generic[InputT]):
    """Builds provider-independent prompt messages from an immutable input DTO.

    Implementations own prompt representation and template policy only. They do
    not execute LLM calls, split batches, validate structured output, or modify
    workflow state.
    """

    def build(self, prompt_input: InputT) -> List[ChatMessage]:
        """Build chat messages for an LLM request."""
