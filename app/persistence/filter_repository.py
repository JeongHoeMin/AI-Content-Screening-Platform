from __future__ import annotations

from typing import Protocol

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collection_filter_result import CollectionFilterSnapshot
from app.persistence.schema import collection_filter_snapshots


class CollectionFilterRepository(Protocol):
    """Harness-owned persistence contract for safe run-input snapshots."""

    async def store(self, snapshot: CollectionFilterSnapshot) -> None:
        """Persist one run snapshot without article content or prompts."""


class SqlAlchemyCollectionFilterRepository(CollectionFilterRepository):
    """Store dashboard collection conditions through an async SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def store(self, snapshot: CollectionFilterSnapshot) -> None:
        await self._session.execute(
            insert(collection_filter_snapshots).values(
                run_id=snapshot.run_id,
                themes=[theme.value for theme in snapshot.themes],
                topics=[topic.value for topic in snapshot.topics],
                catalog_version=snapshot.catalog_version,
                collected_count=snapshot.collected_count,
                accepted_count=snapshot.accepted_count,
                excluded_count=snapshot.excluded_count,
                rejection_counts=snapshot.rejection_counts,
                created_at=snapshot.created_at,
            )
        )
