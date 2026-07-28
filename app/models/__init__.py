"""Domain models."""

from app.models.collect_posts import (
    CollectPostsData,
    CollectPostsMetadata,
    CollectPostsRequest,
    ProviderResultMetadata,
)
from app.models.community import CommunityType
from app.models.normalize import NormalizeResult
from app.models.post import Post
from app.models.raw_post import RawDcInsidePost, RawPost, RawRedditPost

__all__ = [
    "CollectPostsData",
    "CollectPostsMetadata",
    "CollectPostsRequest",
    "CommunityType",
    "NormalizeResult",
    "Post",
    "ProviderResultMetadata",
    "RawDcInsidePost",
    "RawPost",
    "RawRedditPost",
]
