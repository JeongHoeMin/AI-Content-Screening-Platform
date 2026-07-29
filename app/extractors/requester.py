from __future__ import annotations

from typing import List, Protocol

from app.llms.models import ChatMessage, ChatResponse


class NewsEventRequester(Protocol):
    """Forwards prepared news event messages to an LLM client."""

    async def request(self, messages: List[ChatMessage]) -> ChatResponse:
        """Forward one request without copying, interpreting, or wrapping.

        Implementations call LLMClient exactly once with the unchanged message
        list and ``config=None``. They return the unchanged ChatResponse and
        propagate exceptions without wrapping or conversion.
        """
        ...
