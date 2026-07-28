from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl

from app.models.community import CommunityType


class RawPost(BaseModel):
    """Base raw post model returned by community providers."""

    source: CommunityType
    raw_id: str = Field(min_length=1)
    fetched_at: datetime


class RawRedditPost(RawPost):
    """Structured raw Reddit post."""

    source: CommunityType = CommunityType.REDDIT
    subreddit: str = Field(min_length=1)
    title: str = Field(min_length=1)
    selftext: Optional[str] = None
    author_name: Optional[str] = None
    created_at: datetime
    permalink: HttpUrl
    score: int = Field(default=0)
    num_comments: int = Field(default=0, ge=0)


class RawDcInsidePost(RawPost):
    """Structured raw DCInside post."""

    source: CommunityType = CommunityType.DCINSIDE
    gallery_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    body: Optional[str] = None
    nickname: Optional[str] = None
    written_at: datetime
    link: HttpUrl
    views: int = Field(default=0, ge=0)
    recommend_count: int = Field(default=0)
    reply_count: int = Field(default=0, ge=0)
