from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.core import SkillError, SkillMetadata, SkillResult, SkillStage
from app.models import CollectPostsData, CollectPostsMetadata, Post
from app.models.community import CommunityType


def test_skill_metadata_rejects_negative_duration() -> None:
    with pytest.raises(ValidationError):
        SkillMetadata(
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            duration_seconds=-1,
        )


def test_skill_result_supports_collect_posts_generics() -> None:
    now: datetime = datetime.now(timezone.utc)
    post: Post = Post(
        id="post-1",
        source=CommunityType.REDDIT,
        title="Post",
        created_at=now,
        url="https://example.com/posts/1",
    )
    metadata: CollectPostsMetadata = CollectPostsMetadata(
        started_at=now,
        finished_at=now + timedelta(milliseconds=1),
        duration_seconds=0.001,
        provider_results={},
        collected_count=1,
    )

    result: SkillResult[CollectPostsData, CollectPostsMetadata] = SkillResult[
        CollectPostsData,
        CollectPostsMetadata,
    ](
        data=CollectPostsData(posts=[post]),
        metadata=metadata,
        errors=[
            SkillError(
                code="observed_error",
                stage=SkillStage.NORMALIZE,
                message="recoverable observation",
            )
        ],
    )

    assert result.data.posts == [post]
    assert result.metadata.collected_count == 1
    assert result.errors[0].recoverable is True
    assert result.errors[0].stage is SkillStage.NORMALIZE
