from __future__ import annotations

from typing import TypeVar

from app.core.metadata import SkillMetadata
from app.core.request import SkillRequest
from app.core.result import SkillResult
from app.core.skill import Skill

RequestT = TypeVar("RequestT", bound=SkillRequest)
DataT = TypeVar("DataT")
MetadataT = TypeVar("MetadataT", bound=SkillMetadata)


class Harness:
    """Stateless entrypoint for running skills."""

    async def run(
        self,
        skill: Skill[RequestT, DataT, MetadataT],
        request: RequestT,
    ) -> SkillResult[DataT, MetadataT]:
        return await skill.execute(request)
