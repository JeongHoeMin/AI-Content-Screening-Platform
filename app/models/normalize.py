from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, model_validator

from app.core.error import SkillError
from app.models.post import Post


class NormalizeResult(BaseModel):
    """Result of converting a raw post into the common Post model."""

    post: Optional[Post] = None
    error: Optional[SkillError] = None

    @model_validator(mode="after")
    def validate_result(self) -> "NormalizeResult":
        if self.post is None and self.error is None:
            raise ValueError("NormalizeResult must contain a post or an error")
        return self
