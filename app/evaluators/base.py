from __future__ import annotations

from typing import List, Protocol

from app.models.post import Post
from app.models.screen_posts import PostEvaluationResult


class PostEvaluator(Protocol):
    """Evaluates posts and returns screening results."""

    async def evaluate(self, posts: List[Post]) -> PostEvaluationResult:
        """Evaluate a list of posts as a batch."""
