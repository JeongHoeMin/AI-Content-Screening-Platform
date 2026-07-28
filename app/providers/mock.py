from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import List

from app.core.error import SkillError
from app.core.stage import SkillStage
from app.models.collect_posts import CollectPostsRequest
from app.models.community import CommunityType
from app.models.normalize import NormalizeResult
from app.models.post import Post
from app.models.raw_post import RawDcInsidePost, RawPost, RawRedditPost
from app.providers.base import CommunityNormalizer, CommunityProvider


class MockRedditProvider(CommunityProvider):
    """Mock Reddit provider for contract tests."""

    async def collect(self, request: CollectPostsRequest) -> List[RawPost]:
        await asyncio.sleep(0)
        now: datetime = datetime.now(timezone.utc)
        count: int = min(request.limit, 2)
        return [
            RawRedditPost(
                raw_id=f"reddit-{index}",
                fetched_at=now,
                subreddit=request.category or "python",
                title=f"Reddit post {index}",
                selftext=f"Reddit content {index}",
                author_name="reddit_user",
                created_at=now,
                permalink=f"https://reddit.example.com/r/python/comments/{index}",
                score=10 + index,
                num_comments=index,
            )
            for index in range(1, count + 1)
        ]


class MockDcInsideProvider(CommunityProvider):
    """Mock DCInside provider for contract tests."""

    async def collect(self, request: CollectPostsRequest) -> List[RawPost]:
        await asyncio.sleep(0)
        now: datetime = datetime.now(timezone.utc)
        count: int = min(request.limit, 2)
        return [
            RawDcInsidePost(
                raw_id=f"dcinside-{index}",
                fetched_at=now,
                gallery_id=request.category or "programming",
                subject=f"DCInside post {index}",
                body=f"DCInside content {index}",
                nickname="dc_user",
                written_at=now,
                link=f"https://dcinside.example.com/board/view/?id=programming&no={index}",
                views=100 + index,
                recommend_count=5 + index,
                reply_count=index,
            )
            for index in range(1, count + 1)
        ]


class MockRedditNormalizer(CommunityNormalizer):
    """Normalize mock Reddit raw posts."""

    async def normalize(self, raw_post: RawPost) -> NormalizeResult:
        if not isinstance(raw_post, RawRedditPost):
            return NormalizeResult(
                error=SkillError(
                    code="invalid_raw_post_type",
                    stage=SkillStage.NORMALIZE,
                    message="Expected RawRedditPost",
                    source=raw_post.source.value,
                )
            )
        return NormalizeResult(
            post=Post(
                id=raw_post.raw_id,
                source=raw_post.source,
                title=raw_post.title,
                content=raw_post.selftext,
                author=raw_post.author_name,
                created_at=raw_post.created_at,
                url=raw_post.permalink,
                like_count=max(raw_post.score, 0),
                comment_count=raw_post.num_comments,
            )
        )


class MockDcInsideNormalizer(CommunityNormalizer):
    """Normalize mock DCInside raw posts."""

    async def normalize(self, raw_post: RawPost) -> NormalizeResult:
        if not isinstance(raw_post, RawDcInsidePost):
            return NormalizeResult(
                error=SkillError(
                    code="invalid_raw_post_type",
                    stage=SkillStage.NORMALIZE,
                    message="Expected RawDcInsidePost",
                    source=raw_post.source.value,
                )
            )
        return NormalizeResult(
            post=Post(
                id=raw_post.raw_id,
                source=raw_post.source,
                title=raw_post.subject,
                content=raw_post.body,
                author=raw_post.nickname,
                created_at=raw_post.written_at,
                url=raw_post.link,
                view_count=raw_post.views,
                like_count=max(raw_post.recommend_count, 0),
                comment_count=raw_post.reply_count,
            )
        )
