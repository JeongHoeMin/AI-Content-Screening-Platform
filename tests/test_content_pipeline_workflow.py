from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import pytest

from app.core import SkillResult
from app.models import (
    CollectPostsData,
    CollectPostsMetadata,
    CommunityType,
    ContentPipelineRequest,
    ContentPipelineResult,
    GeneratedScript,
    GenerateScriptData,
    GenerateScriptMetadata,
    Post,
    ScreeningResult,
    ScreenPostsData,
    ScreenPostsMetadata,
)
from app.models.collect_posts import ProviderResultMetadata
from app.models.collect_posts import CollectPostsRequest
from app.models.generate_script import GenerateScriptRequest
from app.models.screen_posts import ScreenPostsRequest
from app.workflows import ContentPipelineWorkflow


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class SkillDouble:
    def __init__(self, name: str, result: object = None, error: Exception = None) -> None:
        self.name: str = name
        self.result: object = result
        self.error: Optional[Exception] = error


class HarnessDouble:
    def __init__(self) -> None:
        self.calls: List[str] = []
        self.requests: List[Any] = []

    async def run(self, skill: SkillDouble, request: object) -> object:
        self.calls.append(skill.name)
        self.requests.append(request)
        if skill.error is not None:
            raise skill.error
        return skill.result


def build_post(post_id: str) -> Post:
    return Post(
        id=post_id,
        source=CommunityType.REDDIT,
        title=f"Post {post_id}",
        content="content",
        author="author",
        created_at=datetime.now(timezone.utc),
        url=f"https://example.com/posts/{post_id}",
        like_count=1,
        comment_count=1,
    )


def build_pipeline_parts() -> tuple[
    List[Post],
    List[ScreeningResult],
    List[GeneratedScript],
]:
    posts: List[Post] = [build_post("1"), build_post("2")]
    candidates: List[ScreeningResult] = [
        ScreeningResult(
            post=posts[0],
            score=95,
            is_candidate=True,
            reasons=["후보로 볼 수 있는 이유"],
        )
    ]
    scripts: List[GeneratedScript] = [
        GeneratedScript(
            post=posts[0],
            title="Script title",
            hook="Script hook",
            body="Script body",
            ending="Script ending",
        )
    ]
    return posts, candidates, scripts


def build_collect_result(posts: List[Post]) -> SkillResult[CollectPostsData, CollectPostsMetadata]:
    now: datetime = datetime.now(timezone.utc)
    return SkillResult[CollectPostsData, CollectPostsMetadata](
        data=CollectPostsData(posts=posts),
        metadata=CollectPostsMetadata(
            started_at=now,
            finished_at=now,
            duration_seconds=0.0,
            provider_results={
                CommunityType.REDDIT: ProviderResultMetadata(
                    source=CommunityType.REDDIT,
                    raw_count=len(posts),
                    post_count=len(posts),
                    success=True,
                    duration_seconds=0.0,
                )
            },
            collected_count=len(posts),
        ),
        errors=[],
    )


def build_screen_result(
    candidates: List[ScreeningResult],
) -> SkillResult[ScreenPostsData, ScreenPostsMetadata]:
    now: datetime = datetime.now(timezone.utc)
    return SkillResult[ScreenPostsData, ScreenPostsMetadata](
        data=ScreenPostsData(candidates=candidates),
        metadata=ScreenPostsMetadata(
            started_at=now,
            finished_at=now,
            duration_seconds=0.0,
            total_posts=2,
            candidate_posts=len(candidates),
        ),
        errors=[],
    )


def build_generate_result(
    scripts: List[GeneratedScript],
) -> SkillResult[GenerateScriptData, GenerateScriptMetadata]:
    now: datetime = datetime.now(timezone.utc)
    return SkillResult[GenerateScriptData, GenerateScriptMetadata](
        data=GenerateScriptData(scripts=scripts),
        metadata=GenerateScriptMetadata(
            started_at=now,
            finished_at=now,
            duration_seconds=0.0,
            total_candidates=1,
            generated_scripts=len(scripts),
        ),
        errors=[],
    )


def build_request() -> ContentPipelineRequest:
    return ContentPipelineRequest(
        sources=[CommunityType.REDDIT],
        limit=10,
        period=timedelta(hours=24),
        category="python",
    )


@pytest.mark.anyio
async def test_content_pipeline_runs_skills_in_order_and_combines_results() -> None:
    posts, candidates, scripts = build_pipeline_parts()
    harness: HarnessDouble = HarnessDouble()
    collect_skill: SkillDouble = SkillDouble("collect", build_collect_result(posts))
    screen_skill: SkillDouble = SkillDouble("screen", build_screen_result(candidates))
    generate_skill: SkillDouble = SkillDouble("generate", build_generate_result(scripts))
    workflow: ContentPipelineWorkflow = ContentPipelineWorkflow(
        harness=harness,
        collect_skill=collect_skill,
        screen_skill=screen_skill,
        generate_skill=generate_skill,
    )

    result: ContentPipelineResult = await workflow.run(build_request())

    assert harness.calls == ["collect", "screen", "generate"]
    assert isinstance(result, ContentPipelineResult)
    assert result.posts == posts
    assert result.candidates == candidates
    assert result.scripts == scripts


@pytest.mark.anyio
async def test_content_pipeline_passes_skill_data_to_next_request() -> None:
    posts, candidates, scripts = build_pipeline_parts()
    harness: HarnessDouble = HarnessDouble()
    workflow: ContentPipelineWorkflow = ContentPipelineWorkflow(
        harness=harness,
        collect_skill=SkillDouble("collect", build_collect_result(posts)),
        screen_skill=SkillDouble("screen", build_screen_result(candidates)),
        generate_skill=SkillDouble("generate", build_generate_result(scripts)),
    )
    request: ContentPipelineRequest = build_request()

    await workflow.run(request)

    collect_request = harness.requests[0]
    screen_request = harness.requests[1]
    generate_request = harness.requests[2]
    assert isinstance(collect_request, CollectPostsRequest)
    assert collect_request.sources == request.sources
    assert collect_request.limit == request.limit
    assert collect_request.period == request.period
    assert collect_request.category == request.category
    assert isinstance(screen_request, ScreenPostsRequest)
    assert screen_request.posts == posts
    assert isinstance(generate_request, GenerateScriptRequest)
    assert generate_request.candidates == candidates


@pytest.mark.anyio
async def test_content_pipeline_stops_when_collect_fails() -> None:
    harness: HarnessDouble = HarnessDouble()
    workflow: ContentPipelineWorkflow = ContentPipelineWorkflow(
        harness=harness,
        collect_skill=SkillDouble("collect", error=ValueError("collect failed")),
        screen_skill=SkillDouble("screen"),
        generate_skill=SkillDouble("generate"),
    )

    with pytest.raises(ValueError, match="collect failed"):
        await workflow.run(build_request())

    assert harness.calls == ["collect"]


@pytest.mark.anyio
async def test_content_pipeline_stops_when_screen_fails() -> None:
    posts, _, _ = build_pipeline_parts()
    harness: HarnessDouble = HarnessDouble()
    workflow: ContentPipelineWorkflow = ContentPipelineWorkflow(
        harness=harness,
        collect_skill=SkillDouble("collect", build_collect_result(posts)),
        screen_skill=SkillDouble("screen", error=ValueError("screen failed")),
        generate_skill=SkillDouble("generate"),
    )

    with pytest.raises(ValueError, match="screen failed"):
        await workflow.run(build_request())

    assert harness.calls == ["collect", "screen"]


@pytest.mark.anyio
async def test_content_pipeline_propagates_generate_failure() -> None:
    posts, candidates, _ = build_pipeline_parts()
    harness: HarnessDouble = HarnessDouble()
    workflow: ContentPipelineWorkflow = ContentPipelineWorkflow(
        harness=harness,
        collect_skill=SkillDouble("collect", build_collect_result(posts)),
        screen_skill=SkillDouble("screen", build_screen_result(candidates)),
        generate_skill=SkillDouble("generate", error=ValueError("generate failed")),
    )

    with pytest.raises(ValueError, match="generate failed"):
        await workflow.run(build_request())

    assert harness.calls == ["collect", "screen", "generate"]
