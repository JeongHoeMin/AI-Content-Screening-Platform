from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from app.core.metadata import SkillMetadata
from app.core.request import SkillRequest
from app.models.post import Post
from app.models.screen_posts import ScreeningResult


class GenerateScriptRequest(SkillRequest):
    """Request for generating scripts from screened candidates."""

    candidates: List[ScreeningResult]


class GeneratedScript(BaseModel):
    """Generated shorts script tied to the original post."""

    post: Post
    title: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    body: str = Field(min_length=1)
    ending: str = Field(min_length=1)


class ScriptGenerationResult(BaseModel):
    """Generator output containing all generated scripts."""

    scripts: List[GeneratedScript]


class GenerateScriptData(BaseModel):
    """Business result returned by GenerateScriptSkill."""

    scripts: List[GeneratedScript]


class GenerateScriptMetadata(SkillMetadata):
    """GenerateScript-specific execution metadata."""

    total_candidates: int = Field(ge=0)
    generated_scripts: int = Field(ge=0)
