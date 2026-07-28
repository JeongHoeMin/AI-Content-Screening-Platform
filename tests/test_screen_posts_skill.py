from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pytest

from app.core import SkillResult
from app.evaluators import MockPostEvaluator
from app.harness import Harness
from app.models import (
    CommunityType,
    Post,
    PostEvaluationResult,
    ScreeningResult,
    ScreenPostsData,
    ScreenPostsMetadata,
    ScreenPostsRequest,
)
from app.skills import ScreenPostsSkill


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RecordingEvaluator:
    def __init__(self, result: PostEvaluationResult) -> None:
        self.result: PostEvaluationResult = result
        self.calls: int = 0
        self.received_posts: List[List[Post]] = []

    async def evaluate(self, posts: List[Post]) -> PostEvaluationResult:
        self.calls += 1
        self.received_posts.append(posts)
        return self.result


class FailingEvaluator:
    async def evaluate(self, posts: List[Post]) -> PostEvaluationResult:
        raise ValueError("evaluation failed")


def build_post(
    post_id: str,
    title: str,
    content: str,
    like_count: int,
    comment_count: int,
) -> Post:
    return Post(
        id=post_id,
        source=CommunityType.REDDIT,
        title=title,
        content=content,
        author="author",
        created_at=datetime.now(timezone.utc),
        url=f"https://example.com/posts/{post_id}",
        like_count=like_count,
        comment_count=comment_count,
    )


def build_candidate_result(post: Post, score: int, is_candidate: bool) -> ScreeningResult:
    return ScreeningResult(
        post=post,
        score=score,
        is_candidate=is_candidate,
        reasons=["사람이 읽을 수 있는 평가 설명"],
    )


@pytest.mark.anyio
async def test_mock_post_evaluator_returns_post_evaluation_result() -> None:
    posts: List[Post] = [
        build_post(
            post_id="candidate",
            title="매우 흥미로운 쇼츠 후보 게시글 제목",
            content="본문이 충분히 길어서 영상 소재로 검토할 수 있습니다." * 5,
            like_count=20,
            comment_count=15,
        ),
        build_post(
            post_id="non-candidate",
            title="짧음",
            content="",
            like_count=0,
            comment_count=0,
        ),
    ]
    evaluator: MockPostEvaluator = MockPostEvaluator()

    result: PostEvaluationResult = await evaluator.evaluate(posts)

    assert len(result.posts) == len(posts)
    assert all(0 <= screening.score <= 100 for screening in result.posts)
    assert result.posts[0].is_candidate is True
    assert result.posts[1].is_candidate is False
    assert all(screening.reasons for screening in result.posts)
    assert all(isinstance(reason, str) for screening in result.posts for reason in screening.reasons)


@pytest.mark.anyio
async def test_screen_posts_skill_uses_evaluator_candidates_only_without_sorting() -> None:
    low_score_candidate: Post = build_post("low", "low", "", 0, 0)
    high_score_non_candidate: Post = build_post("high", "high", "", 0, 0)
    middle_candidate: Post = build_post("middle", "middle", "", 0, 0)
    evaluation_result: PostEvaluationResult = PostEvaluationResult(
        posts=[
            build_candidate_result(low_score_candidate, score=10, is_candidate=True),
            build_candidate_result(high_score_non_candidate, score=100, is_candidate=False),
            build_candidate_result(middle_candidate, score=50, is_candidate=True),
        ]
    )
    evaluator: RecordingEvaluator = RecordingEvaluator(evaluation_result)
    skill: ScreenPostsSkill = ScreenPostsSkill(evaluator=evaluator)
    request: ScreenPostsRequest = ScreenPostsRequest(
        posts=[low_score_candidate, high_score_non_candidate, middle_candidate]
    )

    result: SkillResult[ScreenPostsData, ScreenPostsMetadata] = await skill.execute(request)

    assert evaluator.calls == 1
    assert evaluator.received_posts == [request.posts]
    assert [screening.post.id for screening in result.data.candidates] == ["low", "middle"]
    assert [screening.score for screening in result.data.candidates] == [10, 50]
    assert result.metadata.total_posts == 3
    assert result.metadata.candidate_posts == 2
    assert result.errors == []


@pytest.mark.anyio
async def test_screen_posts_skill_propagates_evaluator_failure() -> None:
    skill: ScreenPostsSkill = ScreenPostsSkill(evaluator=FailingEvaluator())
    request: ScreenPostsRequest = ScreenPostsRequest(
        posts=[build_post("post", "title", "content", 1, 1)]
    )

    with pytest.raises(ValueError, match="evaluation failed"):
        await skill.execute(request)


@pytest.mark.anyio
async def test_screen_posts_skill_runs_through_harness() -> None:
    post: Post = build_post("candidate", "candidate", "content", 0, 0)
    evaluation_result: PostEvaluationResult = PostEvaluationResult(
        posts=[build_candidate_result(post, score=1, is_candidate=True)]
    )
    skill: ScreenPostsSkill = ScreenPostsSkill(evaluator=RecordingEvaluator(evaluation_result))
    harness: Harness = Harness()
    request: ScreenPostsRequest = ScreenPostsRequest(posts=[post])

    direct_result: SkillResult[ScreenPostsData, ScreenPostsMetadata] = await skill.execute(request)
    harness_result: SkillResult[ScreenPostsData, ScreenPostsMetadata] = await harness.run(skill, request)

    assert harness_result.data.candidates == direct_result.data.candidates
    assert harness_result.metadata.total_posts == direct_result.metadata.total_posts
    assert harness_result.metadata.candidate_posts == direct_result.metadata.candidate_posts
