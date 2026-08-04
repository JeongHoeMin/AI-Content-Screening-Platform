from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Optional, Protocol

from sqlalchemy import Select, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.schema import source_documents


@dataclass(frozen=True)
class DocumentIdentity:
    """Stable source identity used to prevent repeated extraction work."""

    source: str
    external_id: str
    canonical_url: str
    content_sha256: str

    @classmethod
    def from_content(
        cls,
        *,
        source: str,
        external_id: str,
        canonical_url: str,
        content: str,
    ) -> "DocumentIdentity":
        normalized_content: str = "\n".join(
            line.strip() for line in content.splitlines() if line.strip()
        )
        return cls(
            source=source,
            external_id=external_id,
            canonical_url=canonical_url,
            content_sha256=sha256(normalized_content.encode("utf-8")).hexdigest(),
        )


@dataclass(frozen=True)
class StoredDocument:
    id: str
    identity: DocumentIdentity
    title: str
    published_at: datetime
    analysis_eligible: bool
    quality_status: str


class DocumentRepository(Protocol):
    async def find_existing(self, identity: DocumentIdentity) -> Optional[StoredDocument]:
        """Find a document already persisted under any stable identity."""

    async def store(self, document: StoredDocument, content: str) -> None:
        """Persist one validated source document without emitting its content."""


class SqlAlchemyDocumentRepository(DocumentRepository):
    """Harness-owned async persistence adapter for source document deduplication."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def find_existing(self, identity: DocumentIdentity) -> Optional[StoredDocument]:
        query: Select[tuple[object, ...]] = select(source_documents).where(
            or_(
                (source_documents.c.source == identity.source)
                & (source_documents.c.external_id == identity.external_id),
                source_documents.c.canonical_url == identity.canonical_url,
                source_documents.c.content_sha256 == identity.content_sha256,
            )
        )
        row = (await self._session.execute(query)).mappings().first()
        if row is None:
            return None
        return StoredDocument(
            id=str(row["id"]),
            identity=DocumentIdentity(
                source=str(row["source"]),
                external_id=str(row["external_id"]),
                canonical_url=str(row["canonical_url"]),
                content_sha256=str(row["content_sha256"]),
            ),
            title=str(row["title"]),
            published_at=row["published_at"],
            analysis_eligible=bool(row["analysis_eligible"]),
            quality_status=str(row["quality_status"]),
        )

    async def store(self, document: StoredDocument, content: str) -> None:
        await self._session.execute(
            insert(source_documents).values(
                id=document.id,
                source=document.identity.source,
                external_id=document.identity.external_id,
                canonical_url=document.identity.canonical_url,
                content_sha256=document.identity.content_sha256,
                title=document.title,
                content=content,
                published_at=document.published_at,
                analysis_eligible=int(document.analysis_eligible),
                quality_status=document.quality_status,
                created_at=datetime.utcnow(),
            )
        )
