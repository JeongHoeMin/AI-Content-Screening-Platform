from __future__ import annotations

from typing import Generic, List, TypeVar

from pydantic import BaseModel

from app.core.error import SkillError
from app.core.metadata import SkillMetadata

DataT = TypeVar("DataT")
MetadataT = TypeVar("MetadataT", bound=SkillMetadata)


class SkillResult(BaseModel, Generic[DataT, MetadataT]):
    """Common result envelope returned by skills."""

    data: DataT
    metadata: MetadataT
    errors: List[SkillError]
