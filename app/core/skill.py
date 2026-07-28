from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.core.metadata import SkillMetadata
from app.core.request import SkillRequest
from app.core.result import SkillResult

RequestT = TypeVar("RequestT", bound=SkillRequest)
DataT = TypeVar("DataT")
MetadataT = TypeVar("MetadataT", bound=SkillMetadata)


class Skill(ABC, Generic[RequestT, DataT, MetadataT]):
    """Base contract for every skill."""

    @abstractmethod
    async def execute(self, request: RequestT) -> SkillResult[DataT, MetadataT]:
        """Run the skill and return observed data, metadata, and recoverable errors."""
