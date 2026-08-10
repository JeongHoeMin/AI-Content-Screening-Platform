from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Protocol, Tuple
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
from app.persistence.execution_audit_repository import (
    SqlAlchemyWorkflowExecutionAuditRepository,
)
from app.persistence.schedule_repository import (
    ClaimedScheduledRecommendationJob,
    SqlAlchemyScheduledRecommendationRepository,
)
from app.persistence.price_repository import (
    RecommendationPriceEntry,
    SqlAlchemyRecommendationPriceRepository,
)
from app.models.scheduled_recommendation import ScheduledRecommendationJob

if TYPE_CHECKING:
    from app.harness.execution_audit import WorkflowExecutionAudit


class DocumentPersistence(Protocol):
    """Harness boundary for durable input-document snapshots."""

    async def persist(self, articles: Tuple[Article, ...]) -> None:
        """Store previously unseen inputs without exposing their content to logs."""


class CollectionFilterPersistence(Protocol):
    """Harness boundary for durable, non-content dashboard run conditions."""

    async def persist(self, snapshot: CollectionFilterSnapshot) -> None:
        """Store one safe collection-filter snapshot."""


class WorkflowExecutionAuditPersistence(Protocol):
    """Harness boundary for durable safe workflow terminal observations."""

    async def persist(self, audit: "WorkflowExecutionAudit") -> None:
        """Store one terminal observation without input content or prompts."""


class ScheduledRecommendationPersistence(Protocol):
    """Harness boundary for durable schedule configuration and exclusive leases."""

    async def get(self, job_id: str) -> Optional[ScheduledRecommendationJob]:
        """Load the current schedule configuration, when present."""

    async def save(
        self,
        job: ScheduledRecommendationJob,
        next_run_at: datetime,
        expected_version: Optional[int],
    ) -> None:
        """Persist one validated schedule."""

    async def claim_due(
        self,
        now_utc: datetime,
        lease_owner: str,
        lease_until: datetime,
    ) -> Optional[ClaimedScheduledRecommendationJob]:
        """Lease one due schedule through a short database transaction."""

    async def complete_execution(
        self,
        execution_id: str,
        job_id: str,
        lease_owner: str,
        status: str,
        error_type: Optional[str],
        finished_at: datetime,
    ) -> bool:
        """Persist a bounded terminal status for a claimed schedule slot."""

    async def renew_lease(
        self,
        job_id: str,
        execution_id: str,
        lease_owner: str,
        lease_until: datetime,
    ) -> bool:
        """Extend a live worker lease without exposing database details."""


class RecommendationPricePersistence(Protocol):
    """Harness boundary for immutable recommendation entry price snapshots."""

    async def store_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        """Store safe entry snapshots without overwriting prior observations."""

    async def upsert_latest(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        """Store safe latest snapshots without modifying entry observations."""

    async def backfill_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> int:
        """Recover entry snapshots whose original lookup produced no price."""

    async def list_snapshots(self) -> Tuple[RecommendationPriceEntry, ...]:
        """Load safe snapshots for a Harness-owned performance query."""


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


class SqlAlchemyWorkflowExecutionAuditPersistence:
    """Write safe terminal workflow observations through the Harness boundary."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory

    async def persist(self, audit: "WorkflowExecutionAudit") -> None:
        async with self._session_factory.begin() as session:
            repository: SqlAlchemyWorkflowExecutionAuditRepository = (
                SqlAlchemyWorkflowExecutionAuditRepository(session)
            )
            await repository.store(audit)


class SqlAlchemyScheduledRecommendationPersistence:
    """Persist schedule settings through the worker-owned database boundary."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory

    async def get(self, job_id: str) -> Optional[ScheduledRecommendationJob]:
        async with self._session_factory() as session:
            repository = SqlAlchemyScheduledRecommendationRepository(session)
            return await repository.get(job_id)

    async def save(
        self,
        job: ScheduledRecommendationJob,
        next_run_at: datetime,
        expected_version: Optional[int],
    ) -> None:
        async with self._session_factory.begin() as session:
            repository = SqlAlchemyScheduledRecommendationRepository(session)
            await repository.save(job, next_run_at, expected_version)

    async def claim_due(
        self,
        now_utc: datetime,
        lease_owner: str,
        lease_until: datetime,
    ) -> Optional[ClaimedScheduledRecommendationJob]:
        async with self._session_factory.begin() as session:
            repository = SqlAlchemyScheduledRecommendationRepository(session)
            return await repository.claim_due(now_utc, lease_owner, lease_until)

    async def complete_execution(
        self,
        execution_id: str,
        job_id: str,
        lease_owner: str,
        status: str,
        error_type: Optional[str],
        finished_at: datetime,
    ) -> bool:
        async with self._session_factory.begin() as session:
            repository = SqlAlchemyScheduledRecommendationRepository(session)
            return await repository.complete_execution(
                execution_id=execution_id,
                job_id=job_id,
                lease_owner=lease_owner,
                status=status,
                error_type=error_type,
                finished_at=finished_at,
            )

    async def renew_lease(
        self,
        job_id: str,
        execution_id: str,
        lease_owner: str,
        lease_until: datetime,
    ) -> bool:
        async with self._session_factory.begin() as session:
            repository = SqlAlchemyScheduledRecommendationRepository(session)
            return await repository.renew_lease(
                job_id=job_id,
                execution_id=execution_id,
                lease_owner=lease_owner,
                lease_until=lease_until,
            )


class SqlAlchemyRecommendationPricePersistence:
    """Write recommendation entry price snapshots through the Harness boundary."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] = session_factory

    async def store_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        async with self._session_factory.begin() as session:
            repository: SqlAlchemyRecommendationPriceRepository = (
                SqlAlchemyRecommendationPriceRepository(session)
            )
            await repository.store_entries(snapshots)

    async def upsert_latest(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        """Upsert only LATEST observations in a Harness-owned transaction."""
        async with self._session_factory.begin() as session:
            repository = SqlAlchemyRecommendationPriceRepository(session)
            await repository.upsert_latest(snapshots)

    async def backfill_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> int:
        """Recover unpriced ENTRY observations in a Harness-owned transaction."""
        async with self._session_factory.begin() as session:
            repository = SqlAlchemyRecommendationPriceRepository(session)
            return await repository.backfill_entries(snapshots)

    async def list_snapshots(self) -> Tuple[RecommendationPriceEntry, ...]:
        """Read snapshots through the database adapter, not from Policy or API code."""
        async with self._session_factory() as session:
            repository = SqlAlchemyRecommendationPriceRepository(session)
            return await repository.list_snapshots()
