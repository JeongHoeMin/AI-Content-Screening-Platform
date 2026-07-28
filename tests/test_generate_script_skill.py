from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pytest

from app.core import SkillResult
from app.generators import MockScriptGenerator
from app.harness import Harness
from app.models import (
    CommunityType,
    GeneratedScript,
    GenerateScriptData,
    GenerateScriptMetadata,
    GenerateScriptRequest,
    Post,
    ScreeningResult,
    ScriptGenerationResult,
)
from app.skills import GenerateScriptSkill


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RecordingGenerator:
    def __init__(self, result: ScriptGenerationResult) -> None:
        self.result: ScriptGenerationResult = result
        self.calls: int = 0
        self.received_candidates: List[List[ScreeningResult]] = []

    async def generate(self, candidates: List[ScreeningResult]) -> ScriptGenerationResult:
        self.calls += 1
        self.received_candidates.append(candidates)
        return self.result


class FailingGenerator:
    async def generate(self, candidates: List[ScreeningResult]) -> ScriptGenerationResult:
        raise ValueError("generation failed")


def build_post(post_id: str, title: str) -> Post:
    return Post(
        id=post_id,
        source=CommunityType.REDDIT,
        title=title,
        content="본문",
        author="author",
        created_at=datetime.now(timezone.utc),
        url=f"https://example.com/posts/{post_id}",
        like_count=10,
        comment_count=5,
    )


def build_candidate(post_id: str, title: str) -> ScreeningResult:
    return ScreeningResult(
        post=build_post(post_id, title),
        score=95,
        is_candidate=True,
        reasons=["사람이 읽을 수 있는 후보 선정 이유"],
    )


def build_script(candidate: ScreeningResult) -> GeneratedScript:
    return GeneratedScript(
        post=candidate.post,
        title=f"{candidate.post.title}",
        hook="흥미로운 시작 문장",
        body="핵심 내용을 설명하는 본문",
        ending="여러분은 어떻게 생각하시나요?",
    )


@pytest.mark.anyio
async def test_mock_script_generator_returns_generation_result() -> None:
    candidates: List[ScreeningResult] = [
        build_candidate("post-1", "첫 번째 후보"),
        build_candidate("post-2", "두 번째 후보"),
    ]
    generator: MockScriptGenerator = MockScriptGenerator()

    result: ScriptGenerationResult = await generator.generate(candidates)

    assert len(result.scripts) == len(candidates)
    for script, candidate in zip(result.scripts, candidates):
        assert script.title
        assert script.hook
        assert script.body
        assert script.ending
        assert script.post == candidate.post


@pytest.mark.anyio
async def test_mock_script_generator_returns_empty_result_for_empty_candidates() -> None:
    generator: MockScriptGenerator = MockScriptGenerator()

    result: ScriptGenerationResult = await generator.generate([])

    assert result.scripts == []


@pytest.mark.anyio
async def test_generate_script_skill_delegates_to_generator_without_modifying_scripts() -> None:
    candidate: ScreeningResult = build_candidate("post-1", "후보 게시글")
    generated_script: GeneratedScript = build_script(candidate)
    generation_result: ScriptGenerationResult = ScriptGenerationResult(
        scripts=[generated_script]
    )
    generator: RecordingGenerator = RecordingGenerator(generation_result)
    skill: GenerateScriptSkill = GenerateScriptSkill(generator=generator)
    request: GenerateScriptRequest = GenerateScriptRequest(candidates=[candidate])

    result: SkillResult[GenerateScriptData, GenerateScriptMetadata] = await skill.execute(request)

    assert generator.calls == 1
    assert generator.received_candidates == [request.candidates]
    assert result.data.scripts == generation_result.scripts
    assert result.metadata.total_candidates == 1
    assert result.metadata.generated_scripts == 1
    assert result.errors == []


@pytest.mark.anyio
async def test_generate_script_skill_propagates_generator_failure() -> None:
    skill: GenerateScriptSkill = GenerateScriptSkill(generator=FailingGenerator())
    request: GenerateScriptRequest = GenerateScriptRequest(
        candidates=[build_candidate("post-1", "후보 게시글")]
    )

    with pytest.raises(ValueError, match="generation failed"):
        await skill.execute(request)


@pytest.mark.anyio
async def test_generate_script_skill_runs_through_harness() -> None:
    candidate: ScreeningResult = build_candidate("post-1", "후보 게시글")
    generation_result: ScriptGenerationResult = ScriptGenerationResult(
        scripts=[build_script(candidate)]
    )
    skill: GenerateScriptSkill = GenerateScriptSkill(
        generator=RecordingGenerator(generation_result)
    )
    harness: Harness = Harness()
    request: GenerateScriptRequest = GenerateScriptRequest(candidates=[candidate])

    direct_result: SkillResult[GenerateScriptData, GenerateScriptMetadata] = await skill.execute(request)
    harness_result: SkillResult[GenerateScriptData, GenerateScriptMetadata] = await harness.run(skill, request)

    assert harness_result.data.scripts == direct_result.data.scripts
    assert harness_result.metadata.total_candidates == direct_result.metadata.total_candidates
    assert harness_result.metadata.generated_scripts == direct_result.metadata.generated_scripts
