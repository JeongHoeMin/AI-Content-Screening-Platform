from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.metadata import SkillMetadata
from app.core.request import SkillRequest
from app.models.community import CommunityType
from app.models.post import Post


class CollectPostsRequest(SkillRequest):
    """Request for collecting posts from one or more communities."""

    sources: List[CommunityType] = Field(min_length=1)
    limit: int = Field(gt=0)
    period: timedelta
    category: Optional[str] = None
    ended_at: Optional[datetime] = None

    @field_validator("ended_at")
    @classmethod
    def _normalize_ended_at(cls, value: Optional[datetime]) -> Optional[datetime]:
        """Require a timezone-aware historical collection boundary in UTC."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("ended_at must include a timezone")
        return value.astimezone(timezone.utc)


class CollectPostsData(BaseModel):
    """Business data returned by CollectPostsSkill."""

    posts: List[Post]


class ProviderResultMetadata(BaseModel):
    """Provider-level observations collected during execution."""

    source: CommunityType
    raw_count: int = Field(default=0, ge=0)
    post_count: int = Field(default=0, ge=0)
    normalize_error_count: int = Field(
        default=0,
        ge=0,
        description="RawPost to Post conversion failures; registry lookup failures are not included.",
    )
    success: bool
    duration_seconds: float = Field(ge=0.0)
    error_message: Optional[str] = None


class CollectPostsMetadata(SkillMetadata):
    """CollectPosts-specific execution metadata."""

    provider_results: Dict[CommunityType, ProviderResultMetadata]
    collected_count: int = Field(default=0, ge=0)
