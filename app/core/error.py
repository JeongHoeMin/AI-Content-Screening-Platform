from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class SkillError(BaseModel):
    """Recoverable failure observed during a skill execution."""

    code: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    message: str = Field(min_length=1)
    source: Optional[str] = None
    recoverable: bool = True
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
