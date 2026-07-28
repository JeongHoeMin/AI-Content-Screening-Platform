from __future__ import annotations

from datetime import timedelta
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

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


class CollectPostsData(BaseModel):
    """Business data returned by CollectPostsSkill."""

    posts: List[Post]


class ProviderResultMetadata(BaseModel):
    """Provider-level observations collected during execution."""

    source: CommunityType
    raw_count: int = Field(default=0, ge=0)
    post_count: int = Field(default=0, ge=0)
    success: bool
    duration_seconds: float = Field(ge=0.0)
    error_message: Optional[str] = None


class CollectPostsMetadata(SkillMetadata):
    """CollectPosts-specific execution metadata."""

    provider_results: Dict[CommunityType, ProviderResultMetadata]
    collected_count: int = Field(default=0, ge=0)
