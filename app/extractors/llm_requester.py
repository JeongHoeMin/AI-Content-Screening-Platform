from __future__ import annotations

from typing import List

from app.extractors.requester import NewsEventRequester
from app.llms.base import LLMClient
from app.llms.models import ChatMessage, ChatResponse


class LLMNewsEventRequester(NewsEventRequester):
    """Stateless infrastructure adapter that calls its injected LLM client."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client: LLMClient = llm_client

    async def request(self, messages: List[ChatMessage]) -> ChatResponse:
        return await self._llm_client.chat(messages=messages, config=None)
