from __future__ import annotations

from typing import Generic, List, Protocol, TypeVar

from app.llms.models import ChatMessage

InputT = TypeVar("InputT")


class PromptBuilder(Protocol, Generic[InputT]):
    """Builds chat messages from a builder-specific input DTO."""

    def build(self, prompt_input: InputT) -> List[ChatMessage]:
        """Build chat messages for an LLM request."""
