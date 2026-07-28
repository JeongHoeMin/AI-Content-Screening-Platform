from __future__ import annotations

from typing import List, Optional, Protocol

from app.llms.models import ChatMessage, ChatResponse, GenerationConfig


class LLMClient(Protocol):
    """Chat-based LLM client abstraction."""

    async def chat(
        self,
        messages: List[ChatMessage],
        config: Optional[GenerationConfig] = None,
    ) -> ChatResponse:
        """Return a chat response for the provided messages."""

