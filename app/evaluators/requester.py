from __future__ import annotations

from typing import Protocol, Sequence

from app.llms.models import ChatResponse
from app.models.post import Post


class PostEvaluationRequester(Protocol):
    """Standard orchestration contract for post evaluation requests."""

    async def request(self, posts: Sequence[Post]) -> ChatResponse:
        """Orchestrate one post evaluation request.

        Implementations call PromptBuilder exactly once, forward the resulting
        messages unchanged to LLMClient.chat(messages, config), return the
        unchanged ChatResponse, and never wrap PromptBuilder or LLMClient
        exceptions.
        """
        ...
