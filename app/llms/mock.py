from __future__ import annotations

from typing import List, Optional

from app.llms.base import LLMClient
from app.llms.models import ChatMessage, ChatResponse, GenerationConfig


class MockLLMClient(LLMClient):
    """Stateless LLM client for tests and local development."""

    async def chat(
        self,
        messages: List[ChatMessage],
        config: Optional[GenerationConfig] = None,
    ) -> ChatResponse:
        return ChatResponse(content="Mock Response")
