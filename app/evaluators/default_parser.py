from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence, Set

from app.evaluators.parser import PostEvaluationParser
from app.llms.models import ChatResponse
from app.models.evaluation_response import EvaluationResponse, EvaluationResponseItem
from app.models.post import Post
from app.models.screen_posts import PostEvaluationResult, ScreeningResult


class DefaultPostEvaluationParser(PostEvaluationParser):
    """Assembles domain evaluations from the JSON LLM response contract."""

    def parse(
        self,
        response: ChatResponse,
        posts: Sequence[Post],
    ) -> PostEvaluationResult:
        payload: Any = json.loads(response.content)
        evaluation_response: EvaluationResponse = EvaluationResponse.model_validate(payload)
        posts_by_id: Dict[str, Post] = self._index_posts(posts)
        evaluations_by_id: Dict[str, EvaluationResponseItem] = self._index_evaluations(
            evaluation_response.posts
        )
        self._validate_matching_ids(posts_by_id, evaluations_by_id)

        screening_results: List[ScreeningResult] = [
            ScreeningResult(
                post=post,
                score=evaluations_by_id[post.id].score,
                is_candidate=evaluations_by_id[post.id].is_candidate,
                reasons=evaluations_by_id[post.id].reasons,
            )
            for post in posts
        ]
        return PostEvaluationResult(posts=screening_results)

    @staticmethod
    def _index_posts(posts: Sequence[Post]) -> Dict[str, Post]:
        posts_by_id: Dict[str, Post] = {post.id: post for post in posts}
        if len(posts_by_id) != len(posts):
            raise ValueError("Input posts contain duplicate IDs")
        return posts_by_id

    @staticmethod
    def _index_evaluations(
        evaluations: Sequence[EvaluationResponseItem],
    ) -> Dict[str, EvaluationResponseItem]:
        evaluations_by_id: Dict[str, EvaluationResponseItem] = {
            evaluation.post_id: evaluation for evaluation in evaluations
        }
        if len(evaluations_by_id) != len(evaluations):
            raise ValueError("Evaluation response contains duplicate post IDs")
        return evaluations_by_id

    @staticmethod
    def _validate_matching_ids(
        posts_by_id: Dict[str, Post],
        evaluations_by_id: Dict[str, EvaluationResponseItem],
    ) -> None:
        post_ids: Set[str] = set(posts_by_id)
        evaluation_ids: Set[str] = set(evaluations_by_id)
        if post_ids != evaluation_ids:
            raise ValueError("Evaluation response post IDs do not match input posts")
