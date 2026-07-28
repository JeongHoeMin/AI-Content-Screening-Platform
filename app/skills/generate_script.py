from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from app.core.result import SkillResult
from app.core.skill import Skill
from app.generators.base import ScriptGenerator
from app.models.generate_script import (
    GenerateScriptData,
    GenerateScriptMetadata,
    GenerateScriptRequest,
)


class GenerateScriptSkill(
    Skill[GenerateScriptRequest, GenerateScriptData, GenerateScriptMetadata]
):
    """Runs a script generator and wraps its output in a SkillResult."""

    def __init__(self, generator: ScriptGenerator) -> None:
        self._generator: ScriptGenerator = generator

    async def execute(
        self,
        request: GenerateScriptRequest,
    ) -> SkillResult[GenerateScriptData, GenerateScriptMetadata]:
        started_at: datetime = datetime.now(timezone.utc)
        execution_started: float = perf_counter()

        generation = await self._generator.generate(request.candidates)

        finished_at: datetime = datetime.now(timezone.utc)
        return SkillResult[GenerateScriptData, GenerateScriptMetadata](
            data=GenerateScriptData(scripts=generation.scripts),
            metadata=GenerateScriptMetadata(
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=perf_counter() - execution_started,
                total_candidates=len(request.candidates),
                generated_scripts=len(generation.scripts),
            ),
            errors=[],
        )
