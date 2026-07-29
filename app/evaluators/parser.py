from __future__ import annotations

from typing import Protocol, Sequence

from app.llms.models import ChatResponse
from app.models.post import Post
from app.models.screen_posts import PostEvaluationResult


class PostEvaluationParser(Protocol):
    """Converts one LLM response and its source posts into a domain result."""

    def parse(
        self,
        response: ChatResponse,
        posts: Sequence[Post],
    ) -> PostEvaluationResult:
        """Parse, map, and assemble one complete post evaluation result."""
        ...
