from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import List, Tuple

import structlog

from app.core.error import SkillError
from app.core.exceptions import AllProvidersFailedError
from app.core.result import SkillResult
from app.core.skill import Skill
from app.core.stage import SkillStage
from app.models.collect_posts import (
    CollectPostsData,
    CollectPostsMetadata,
    CollectPostsRequest,
    ProviderResultMetadata,
)
from app.models.community import CommunityType
from app.models.post import Post
from app.models.raw_post import RawPost
from app.providers.registry import NormalizerRegistry, ProviderRegistry

logger = structlog.get_logger(__name__)


@dataclass
class ProviderExecution:
    __slots__ = ("source", "raw_posts", "metadata", "errors")

    source: CommunityType
    raw_posts: List[RawPost]
    metadata: ProviderResultMetadata
    errors: List[SkillError]


class CollectPostsSkill(Skill[CollectPostsRequest, CollectPostsData, CollectPostsMetadata]):
    """Collect raw posts from providers and normalize them into common Post models."""

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        normalizer_registry: NormalizerRegistry,
    ) -> None:
        self._provider_registry: ProviderRegistry = provider_registry
        self._normalizer_registry: NormalizerRegistry = normalizer_registry

    async def execute(
        self,
        request: CollectPostsRequest,
    ) -> SkillResult[CollectPostsData, CollectPostsMetadata]:
        started_at: datetime = datetime.now(timezone.utc)
        execution_started: float = perf_counter()

        provider_results: List[ProviderExecution] = await asyncio.gather(
            *(self._collect_from_provider(source, request) for source in request.sources)
        )

        posts: List[Post] = []
        errors: List[SkillError] = []
        metadata_by_source: dict[CommunityType, ProviderResultMetadata] = {}

        for execution in provider_results:
            errors.extend(execution.errors)
            normalized_posts, normalize_errors, normalize_error_count = await self._normalize_posts(
                execution.source,
                execution.raw_posts,
            )
            posts.extend(normalized_posts)
            errors.extend(normalize_errors)

            execution.metadata.post_count = len(normalized_posts)
            execution.metadata.normalize_error_count = normalize_error_count
            metadata_by_source[execution.source] = execution.metadata

        if not posts and all(not provider_metadata.success for provider_metadata in metadata_by_source.values()):
            raise AllProvidersFailedError()

        finished_at: datetime = datetime.now(timezone.utc)
        metadata: CollectPostsMetadata = self._build_metadata(
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=perf_counter() - execution_started,
            provider_results=metadata_by_source,
            collected_count=len(posts),
        )
        return SkillResult[CollectPostsData, CollectPostsMetadata](
            data=CollectPostsData(posts=posts),
            metadata=metadata,
            errors=errors,
        )

    async def _collect_from_provider(
        self,
        source: CommunityType,
        request: CollectPostsRequest,
    ) -> ProviderExecution:
        started: float = perf_counter()
        logger.info("provider_collect_start", source=source.value)

        try:
            provider = self._provider_registry.get(source)
            raw_posts: List[RawPost] = await provider.collect(request)
        except Exception as exc:
            duration_seconds: float = perf_counter() - started
            logger.warning(
                "provider_collect_failed",
                source=source.value,
                duration_seconds=duration_seconds,
                error=str(exc),
            )
            metadata: ProviderResultMetadata = ProviderResultMetadata(
                source=source,
                raw_count=0,
                post_count=0,
                success=False,
                duration_seconds=duration_seconds,
                error_message=str(exc),
            )
            error: SkillError = SkillError(
                code="provider_collect_failed",
                stage=SkillStage.PROVIDER_COLLECT,
                message=str(exc),
                source=source.value,
            )
            return ProviderExecution(
                source=source,
                raw_posts=[],
                metadata=metadata,
                errors=[error],
            )

        duration_seconds = perf_counter() - started
        logger.info(
            "provider_collect_success",
            source=source.value,
            raw_count=len(raw_posts),
            duration_seconds=duration_seconds,
        )
        metadata = ProviderResultMetadata(
            source=source,
            raw_count=len(raw_posts),
            post_count=0,
            success=True,
            duration_seconds=duration_seconds,
        )
        return ProviderExecution(
            source=source,
            raw_posts=raw_posts,
            metadata=metadata,
            errors=[],
        )

    async def _normalize_posts(
        self,
        source: CommunityType,
        raw_posts: List[RawPost],
    ) -> Tuple[List[Post], List[SkillError], int]:
        posts: List[Post] = []
        errors: List[SkillError] = []
        normalize_error_count: int = 0

        try:
            normalizer = self._normalizer_registry.get(source)
        except Exception as exc:
            return [], [
                SkillError(
                    code="normalizer_not_found",
                    stage=SkillStage.NORMALIZE,
                    message=str(exc),
                    source=source.value,
                )
            ], 0

        for raw_post in raw_posts:
            try:
                normalize_result = await normalizer.normalize(raw_post)
            except Exception as exc:
                normalize_error_count += 1
                errors.append(
                    SkillError(
                        code="normalizer_failed",
                        stage=SkillStage.NORMALIZE,
                        message=str(exc),
                        source=source.value,
                    )
                )
                continue

            if normalize_result.post is not None:
                posts.append(normalize_result.post)
            if normalize_result.error is not None:
                normalize_error_count += 1
                errors.append(normalize_result.error)

        return posts, errors, normalize_error_count

    def _build_metadata(
        self,
        started_at: datetime,
        finished_at: datetime,
        duration_seconds: float,
        provider_results: dict[CommunityType, ProviderResultMetadata],
        collected_count: int,
    ) -> CollectPostsMetadata:
        return CollectPostsMetadata(
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            provider_results=provider_results,
            collected_count=collected_count,
        )
