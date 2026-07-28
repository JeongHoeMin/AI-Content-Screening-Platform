from __future__ import annotations

from typing import List

from app.models.post import Post
from app.models.screen_posts import PostEvaluationResult, ScreeningResult


class MockPostEvaluator:
    """Stateless mock evaluator for screening contract tests."""

    _candidate_threshold: int = 90

    async def evaluate(self, posts: List[Post]) -> PostEvaluationResult:
        return PostEvaluationResult(posts=[self._evaluate_post(post) for post in posts])

    def _evaluate_post(self, post: Post) -> ScreeningResult:
        title_score: int = min(len(post.title), 30)
        content_score: int = min(len(post.content or "") // 5, 25)
        like_score: int = min(post.like_count * 2, 25)
        comment_score: int = min(post.comment_count * 2, 20)
        score: int = min(title_score + content_score + like_score + comment_score, 100)

        reasons: List[str] = [
            f"제목 길이가 {len(post.title)}자로 관심을 끌 수 있음",
            f"좋아요 {post.like_count}개와 댓글 {post.comment_count}개가 관찰됨",
        ]
        if post.content:
            reasons.append("본문 내용이 있어 쇼츠 소재 검토가 가능함")
        else:
            reasons.append("본문이 없어 제목과 반응 지표 중심으로 평가함")

        return ScreeningResult(
            post=post,
            score=score,
            is_candidate=score >= self._candidate_threshold,
            reasons=reasons,
        )
