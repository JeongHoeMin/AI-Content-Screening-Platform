from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.community import CommunityType
from app.models.generate_script import GeneratedScript
from app.models.post import Post
from app.models.screen_posts import ScreeningResult


class ContentPipelineRequest(BaseModel):
    """Minimal input for running the content pipeline workflow."""

    sources: List[CommunityType] = Field(min_length=1)
    limit: int = Field(gt=0)
    period: timedelta
    category: Optional[str] = None


class ContentPipelineResult(BaseModel):
    """Workflow-level result composed from pipeline skill outputs."""

    posts: List[Post]
    candidates: List[ScreeningResult]
    scripts: List[GeneratedScript]
