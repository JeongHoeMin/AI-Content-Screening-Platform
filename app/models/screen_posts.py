from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from app.core.metadata import SkillMetadata
from app.core.request import SkillRequest
from app.models.post import Post


class ScreenPostsRequest(SkillRequest):
    """Request for screening posts into shorts candidates."""

    posts: List[Post]


class ScreeningResult(BaseModel):
    """Evaluation result for a single post."""

    post: Post
    score: int = Field(ge=0, le=100)
    is_candidate: bool
    reasons: List[str] = Field(min_length=1)


class PostEvaluationResult(BaseModel):
    """Evaluator output containing all post evaluation results."""

    posts: List[ScreeningResult]


class ScreenPostsData(BaseModel):
    """Business result containing final shorts candidates."""

    candidates: List[ScreeningResult]


class ScreenPostsMetadata(SkillMetadata):
    """ScreenPosts-specific execution metadata."""

    total_posts: int = Field(ge=0)
    candidate_posts: int = Field(ge=0)
