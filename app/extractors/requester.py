from __future__ import annotations

from typing import List, Protocol

from app.llms.models import ChatMessage, ChatResponse


class NewsEventRequester(Protocol):
    """Defines forwarding of a prepared news event request."""

    async def request(self, messages: List[ChatMessage]) -> ChatResponse:
        """Forward prepared messages while preserving their identity.

        Implementations do not copy or interpret the input messages, and they
        return the received ChatResponse unchanged. Exceptions propagate
        without wrapping or conversion.
        """
        ...
