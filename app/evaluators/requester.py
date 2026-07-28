from __future__ import annotations

from typing import Protocol, Sequence

from app.llms.models import ChatResponse
from app.models.post import Post


class PostEvaluationRequester(Protocol):
    """Standard orchestration contract for post evaluation requests."""

    async def request(self, posts: Sequence[Post]) -> ChatResponse:
        """Build one prompt request and return the unchanged LLM response.

        Implementations call PromptBuilder once, pass its unchanged message
        collection to LLMClient.chat(messages, config), and return the unchanged
        ChatResponse. PromptBuilder and LLMClient exceptions are not wrapped.
        """
        ...
