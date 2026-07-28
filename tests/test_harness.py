from __future__ import annotations

import asyncio
from datetime import timedelta

from app.core import SkillResult
from app.harness import Harness
from app.models import CollectPostsData, CollectPostsMetadata, CollectPostsRequest, CommunityType
from app.providers import (
    MockDcInsideNormalizer,
    MockDcInsideProvider,
    MockRedditNormalizer,
    MockRedditProvider,
    NormalizerRegistry,
    ProviderRegistry,
)
from app.skills import CollectPostsSkill


def build_skill() -> CollectPostsSkill:
    return CollectPostsSkill(
        provider_registry=ProviderRegistry(
            {
                CommunityType.REDDIT: MockRedditProvider(),
                CommunityType.DCINSIDE: MockDcInsideProvider(),
            }
        ),
        normalizer_registry=NormalizerRegistry(
            {
                CommunityType.REDDIT: MockRedditNormalizer(),
                CommunityType.DCINSIDE: MockDcInsideNormalizer(),
            }
        ),
    )


def build_request(limit: int) -> CollectPostsRequest:
    return CollectPostsRequest(
        sources=[CommunityType.REDDIT, CommunityType.DCINSIDE],
        limit=limit,
        period=timedelta(hours=24),
    )


def test_harness_run_matches_direct_skill_execution() -> None:
    skill: CollectPostsSkill = build_skill()
    harness: Harness = Harness()
    request: CollectPostsRequest = build_request(limit=2)

    direct_result: SkillResult[CollectPostsData, CollectPostsMetadata] = asyncio.run(
        skill.execute(request)
    )
    harness_result: SkillResult[CollectPostsData, CollectPostsMetadata] = asyncio.run(
        harness.run(skill, request)
    )

    assert [post.id for post in harness_result.data.posts] == [
        post.id for post in direct_result.data.posts
    ]
    assert [post.source for post in harness_result.data.posts] == [
        post.source for post in direct_result.data.posts
    ]
    assert harness_result.metadata.collected_count == direct_result.metadata.collected_count
    assert harness_result.metadata.provider_results.keys() == direct_result.metadata.provider_results.keys()
    assert harness_result.errors == direct_result.errors


def test_harness_reuse_does_not_leak_execution_state() -> None:
    skill: CollectPostsSkill = build_skill()
    harness: Harness = Harness()

    first_result: SkillResult[CollectPostsData, CollectPostsMetadata] = asyncio.run(
        harness.run(skill, build_request(limit=1))
    )
    second_result: SkillResult[CollectPostsData, CollectPostsMetadata] = asyncio.run(
        harness.run(skill, build_request(limit=2))
    )

    assert first_result.metadata.collected_count == 2
    assert second_result.metadata.collected_count == 4
    assert first_result.data.posts != second_result.data.posts
