from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

from app.core.error import SkillError
from app.models import (
    CollectPostsRequest,
    CommunityType,
    NormalizeResult,
    RawPost,
    RawRedditPost,
)
from app.providers import (
    CommunityNormalizer,
    CommunityProvider,
    MockDcInsideNormalizer,
    MockDcInsideProvider,
    MockRedditNormalizer,
    MockRedditProvider,
    NormalizerRegistry,
    ProviderRegistry,
)
from app.skills import CollectPostsSkill


class FailingProvider(CommunityProvider):
    async def collect(self, request: CollectPostsRequest) -> List[RawPost]:
        raise TimeoutError("provider timed out")


class SlowProvider(CommunityProvider):
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds: float = delay_seconds

    async def collect(self, request: CollectPostsRequest) -> List[RawPost]:
        await asyncio.sleep(self.delay_seconds)
        now: datetime = datetime.now(timezone.utc)
        return [
            RawRedditPost(
                raw_id="slow-reddit-1",
                fetched_at=now,
                subreddit="python",
                title="Slow Reddit post",
                created_at=now,
                permalink="https://reddit.example.com/r/python/comments/slow",
            )
        ]


class ErrorNormalizer(CommunityNormalizer):
    def normalize(self, raw_post: RawPost) -> NormalizeResult:
        return NormalizeResult(
            error=SkillError(
                code="normalization_skipped",
                stage="normalize",
                message="raw post could not be normalized",
                source=raw_post.source.value,
            )
        )


def build_request() -> CollectPostsRequest:
    return CollectPostsRequest(
        sources=[CommunityType.REDDIT, CommunityType.DCINSIDE],
        limit=2,
        period=timedelta(hours=24),
    )


def test_collect_posts_merges_mock_provider_results() -> None:
    skill: CollectPostsSkill = CollectPostsSkill(
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

    result = asyncio.run(skill.execute(build_request()))

    assert len(result.data.posts) == 4
    assert result.metadata.collected_count == 4
    assert result.metadata.provider_results[CommunityType.REDDIT].raw_count == 2
    assert result.metadata.provider_results[CommunityType.DCINSIDE].post_count == 2
    assert result.errors == []


def test_provider_failure_is_recorded_without_stopping_successful_provider() -> None:
    skill: CollectPostsSkill = CollectPostsSkill(
        provider_registry=ProviderRegistry(
            {
                CommunityType.REDDIT: MockRedditProvider(),
                CommunityType.DCINSIDE: FailingProvider(),
            }
        ),
        normalizer_registry=NormalizerRegistry(
            {
                CommunityType.REDDIT: MockRedditNormalizer(),
                CommunityType.DCINSIDE: MockDcInsideNormalizer(),
            }
        ),
    )

    result = asyncio.run(skill.execute(build_request()))

    assert len(result.data.posts) == 2
    assert result.metadata.provider_results[CommunityType.REDDIT].success is True
    assert result.metadata.provider_results[CommunityType.DCINSIDE].success is False
    assert [error.code for error in result.errors] == ["provider_collect_failed"]


def test_all_provider_failures_raise_exception() -> None:
    skill: CollectPostsSkill = CollectPostsSkill(
        provider_registry=ProviderRegistry(
            {
                CommunityType.REDDIT: FailingProvider(),
                CommunityType.DCINSIDE: FailingProvider(),
            }
        ),
        normalizer_registry=NormalizerRegistry({}),
    )

    try:
        asyncio.run(skill.execute(build_request()))
    except RuntimeError as exc:
        assert "all providers failed" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for all provider failures")


def test_normalizer_error_is_recorded_as_recoverable_observation() -> None:
    skill: CollectPostsSkill = CollectPostsSkill(
        provider_registry=ProviderRegistry({CommunityType.REDDIT: MockRedditProvider()}),
        normalizer_registry=NormalizerRegistry({CommunityType.REDDIT: ErrorNormalizer()}),
    )
    request: CollectPostsRequest = CollectPostsRequest(
        sources=[CommunityType.REDDIT],
        limit=1,
        period=timedelta(hours=1),
    )

    result = asyncio.run(skill.execute(request))

    assert result.data.posts == []
    assert result.errors[0].code == "normalization_skipped"
    assert result.metadata.provider_results[CommunityType.REDDIT].success is True


def test_providers_run_in_parallel() -> None:
    skill: CollectPostsSkill = CollectPostsSkill(
        provider_registry=ProviderRegistry(
            {
                CommunityType.REDDIT: SlowProvider(delay_seconds=0.05),
                CommunityType.DCINSIDE: SlowProvider(delay_seconds=0.05),
            }
        ),
        normalizer_registry=NormalizerRegistry(
            {
                CommunityType.REDDIT: MockRedditNormalizer(),
                CommunityType.DCINSIDE: MockRedditNormalizer(),
            }
        ),
    )
    request: CollectPostsRequest = build_request()
    started_at: datetime = datetime.now(timezone.utc)

    asyncio.run(skill.execute(request))

    elapsed_seconds: float = (datetime.now(timezone.utc) - started_at).total_seconds()
    assert elapsed_seconds < 0.09


def test_registries_register_and_get_entries() -> None:
    provider_registry: ProviderRegistry = ProviderRegistry({})
    normalizer_registry: NormalizerRegistry = NormalizerRegistry({})
    provider: MockRedditProvider = MockRedditProvider()
    normalizer: MockRedditNormalizer = MockRedditNormalizer()

    provider_registry.register(CommunityType.REDDIT, provider)
    normalizer_registry.register(CommunityType.REDDIT, normalizer)

    assert provider_registry.get(CommunityType.REDDIT) is provider
    assert normalizer_registry.get(CommunityType.REDDIT) is normalizer
