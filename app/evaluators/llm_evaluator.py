from __future__ import annotations

from typing import List

from app.evaluators.base import PostEvaluator
from app.evaluators.parser import PostEvaluationParser
from app.evaluators.requester import PostEvaluationRequester
from app.llms.models import ChatResponse
from app.models.post import Post
from app.models.screen_posts import PostEvaluationResult


class LLMPostEvaluator(PostEvaluator):
    """Orchestrates request and parsing contracts for post evaluation."""

    def __init__(
        self,
        requester: PostEvaluationRequester,
        parser: PostEvaluationParser,
    ) -> None:
        self._requester: PostEvaluationRequester = requester
        self._parser: PostEvaluationParser = parser

    async def evaluate(self, posts: List[Post]) -> PostEvaluationResult:
        response: ChatResponse = await self._requester.request(posts)
        return self._parser.parse(response, posts)
