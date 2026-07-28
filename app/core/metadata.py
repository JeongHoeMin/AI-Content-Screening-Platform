from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator


class SkillMetadata(BaseModel):
    """Base metadata observed during skill execution."""

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_finished_at(self) -> "SkillMetadata":
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must be greater than or equal to started_at")
        return self
