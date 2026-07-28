from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from app.models.collect_posts import CollectPostsRequest
from app.models.normalize import NormalizeResult
from app.models.raw_post import RawPost


class CommunityProvider(ABC):
    """Collects raw posts from a community."""

    @abstractmethod
    async def collect(self, request: CollectPostsRequest) -> List[RawPost]:
        """Return raw posts without normalizing them."""


class CommunityNormalizer(ABC):
    """Converts raw community posts into normalized posts."""

    @abstractmethod
    async def normalize(self, raw_post: RawPost) -> NormalizeResult:
        """Return a normalized post or a recoverable normalization error."""
