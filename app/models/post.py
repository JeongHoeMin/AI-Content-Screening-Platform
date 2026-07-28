from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl

from app.models.community import CommunityType


class Post(BaseModel):
    """Normalized post used across the platform."""

    id: str = Field(min_length=1)
    source: CommunityType
    title: str = Field(min_length=1)
    content: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime
    url: HttpUrl
    view_count: int = Field(default=0, ge=0)
    like_count: int = Field(default=0, ge=0)
    comment_count: int = Field(default=0, ge=0)
