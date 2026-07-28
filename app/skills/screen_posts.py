from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import List

from app.core.result import SkillResult
from app.core.skill import Skill
from app.evaluators.base import PostEvaluator
from app.models.screen_posts import (
    ScreenPostsData,
    ScreenPostsMetadata,
    ScreenPostsRequest,
    ScreeningResult,
)


class ScreenPostsSkill(Skill[ScreenPostsRequest, ScreenPostsData, ScreenPostsMetadata]):
    """Screens evaluated posts into shorts candidates."""

    def __init__(self, evaluator: PostEvaluator) -> None:
        self._evaluator: PostEvaluator = evaluator

    async def execute(
        self,
        request: ScreenPostsRequest,
    ) -> SkillResult[ScreenPostsData, ScreenPostsMetadata]:
        started_at: datetime = datetime.now(timezone.utc)
        execution_started: float = perf_counter()

        evaluation = await self._evaluator.evaluate(request.posts)
        candidates: List[ScreeningResult] = [
            screening for screening in evaluation.posts if screening.is_candidate is True
        ]

        finished_at: datetime = datetime.now(timezone.utc)
        return SkillResult[ScreenPostsData, ScreenPostsMetadata](
            data=ScreenPostsData(candidates=candidates),
            metadata=ScreenPostsMetadata(
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=perf_counter() - execution_started,
                total_posts=len(request.posts),
                candidate_posts=len(candidates),
            ),
            errors=[],
        )
