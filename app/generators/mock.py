from __future__ import annotations

from typing import List

from app.models.generate_script import GeneratedScript, ScriptGenerationResult
from app.models.screen_posts import ScreeningResult


class MockScriptGenerator:
    """Stateless template-based script generator for contract tests."""

    async def generate(self, candidates: List[ScreeningResult]) -> ScriptGenerationResult:
        return ScriptGenerationResult(
            scripts=[self._generate_script(candidate) for candidate in candidates]
        )

    def _generate_script(self, candidate: ScreeningResult) -> GeneratedScript:
        post = candidate.post
        return GeneratedScript(
            post=post,
            title=f"{post.title}",
            hook=f"{post.title}, 이 이야기는 지금 바로 볼 만합니다.",
            body=(
                f"{post.title}에 대한 반응이 이어지고 있습니다. "
                f"좋아요 {post.like_count}개와 댓글 {post.comment_count}개가 관찰되었습니다."
            ),
            ending="여러분은 어떻게 생각하시나요?",
        )
