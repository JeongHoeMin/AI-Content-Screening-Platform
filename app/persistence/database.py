from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config.persistence import DatabaseConfig
from app.persistence.harness_adapter import (
    SqlAlchemyCollectionFilterPersistence,
    SqlAlchemyDocumentPersistence,
    SqlAlchemyWorkflowExecutionAuditPersistence,
)


def create_session_factory(
    config: DatabaseConfig,
) -> async_sessionmaker[AsyncSession]:
    """Create the harness-owned async database boundary from validated settings."""
    engine: AsyncEngine = create_async_engine(config.url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)


def create_document_persistence(config: DatabaseConfig) -> SqlAlchemyDocumentPersistence:
    """Assemble the Harness-owned document persistence adapter."""
    return SqlAlchemyDocumentPersistence(create_session_factory(config))


def create_collection_filter_persistence(
    config: DatabaseConfig,
) -> SqlAlchemyCollectionFilterPersistence:
    """Assemble the Harness-owned collection-filter persistence adapter."""
    return SqlAlchemyCollectionFilterPersistence(create_session_factory(config))


def create_workflow_execution_audit_persistence(
    config: DatabaseConfig,
) -> SqlAlchemyWorkflowExecutionAuditPersistence:
    """Assemble durable safe workflow audit persistence for a Harness."""
    return SqlAlchemyWorkflowExecutionAuditPersistence(create_session_factory(config))
