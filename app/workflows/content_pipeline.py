from __future__ import annotations

from app.harness import Harness
from app.models.collect_posts import CollectPostsRequest
from app.models.generate_script import GenerateScriptRequest
from app.models.screen_posts import ScreenPostsRequest
from app.models.workflow import ContentPipelineRequest, ContentPipelineResult
from app.skills.collect_posts import CollectPostsSkill
from app.skills.generate_script import GenerateScriptSkill
from app.skills.screen_posts import ScreenPostsSkill
from app.workflows.base import Workflow


class ContentPipelineWorkflow(Workflow[ContentPipelineRequest, ContentPipelineResult]):
    """Runs collect, screen, and generate skills in sequence through a harness."""

    def __init__(
        self,
        harness: Harness,
        collect_skill: CollectPostsSkill,
        screen_skill: ScreenPostsSkill,
        generate_skill: GenerateScriptSkill,
    ) -> None:
        self._harness: Harness = harness
        self._collect_skill: CollectPostsSkill = collect_skill
        self._screen_skill: ScreenPostsSkill = screen_skill
        self._generate_skill: GenerateScriptSkill = generate_skill

    async def run(self, request: ContentPipelineRequest) -> ContentPipelineResult:
        collect_result = await self._harness.run(
            self._collect_skill,
            CollectPostsRequest(
                sources=request.sources,
                limit=request.limit,
                period=request.period,
                category=request.category,
            ),
        )
        screen_result = await self._harness.run(
            self._screen_skill,
            ScreenPostsRequest(posts=collect_result.data.posts),
        )
        generate_result = await self._harness.run(
            self._generate_skill,
            GenerateScriptRequest(candidates=screen_result.data.candidates),
        )
        return ContentPipelineResult(
            posts=collect_result.data.posts,
            candidates=screen_result.data.candidates,
            scripts=generate_result.data.scripts,
        )
