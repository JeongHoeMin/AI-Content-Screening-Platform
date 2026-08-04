from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.article import Article
from app.models.collection_filter_result import CollectionFilterSnapshot
from app.persistence.repository import (
    DocumentIdentity,
    SqlAlchemyDocumentRepository,
    StoredDocument,
)
from app.persistence.filter_repository import SqlAlchemyCollectionFilterRepository


class DocumentPersistence(Protocol):
    """Harness boundary for durable input-document snapshots."""

    async def persist(self, articles: Tuple[Article, ...]) -> None:
        """Store previously unseen inputs without exposing their content to logs."""


class CollectionFilterPersistence(Protocol):
    """Harness boundary for durable, non-content dashboard run conditions."""

    async def persist(self, snapshot: CollectionFilterSnapshot) -> None:
        """Store one safe collection-filter snapshot."""


class SqlAlchemyDocumentPersistence:
    """Write source documents once through a Harness-owned async session."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory

    async def persist(self, articles: Tuple[Article, ...]) -> None:
        """Store stable document identities and skip already known snapshots."""
        async with self._session_factory.begin() as session:
            repository: SqlAlchemyDocumentRepository = SqlAlchemyDocumentRepository(session)
            for article in articles:
                identity: DocumentIdentity = DocumentIdentity.from_content(
                    source=article.source,
                    external_id=article.id,
                    canonical_url=str(article.url),
                    content=article.content,
                )
                if await repository.find_existing(identity) is not None:
                    continue
                await repository.store(
                    StoredDocument(
                        id=str(uuid4()),
                        identity=identity,
                        title=article.title,
                        published_at=article.published_at,
                        analysis_eligible=True,
                        quality_status="received",
                    ),
                    article.content,
                )


class SqlAlchemyCollectionFilterPersistence:
    """Write dashboard filter conditions through the Harness-owned database boundary."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory

    async def persist(self, snapshot: CollectionFilterSnapshot) -> None:
        async with self._session_factory.begin() as session:
            repository: SqlAlchemyCollectionFilterRepository = (
                SqlAlchemyCollectionFilterRepository(session)
            )
            await repository.store(snapshot)
