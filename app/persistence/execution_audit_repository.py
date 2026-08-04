from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.schema import workflow_execution_audits

if TYPE_CHECKING:
    from app.harness.execution_audit import WorkflowExecutionAudit


class WorkflowExecutionAuditRepository(Protocol):
    """Harness-owned persistence contract for safe workflow terminal observations."""

    async def store(self, audit: "WorkflowExecutionAudit") -> None:
        """Persist one safe terminal observation without input content or prompts."""


class SqlAlchemyWorkflowExecutionAuditRepository(WorkflowExecutionAuditRepository):
    """Persist safe workflow terminal observations with an async SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def store(self, audit: "WorkflowExecutionAudit") -> None:
        await self._session.execute(
            insert(workflow_execution_audits).values(
                execution_id=audit.execution_id,
                execution_mode=audit.execution_mode,
                status=audit.status.value,
                started_at=audit.started_at,
                finished_at=audit.finished_at,
                duration_seconds=audit.duration_seconds,
                input_article_count=audit.input_article_count,
                statistics=(
                    audit.statistics.model_dump(mode="json")
                    if audit.statistics is not None
                    else None
                ),
                error_type=audit.error_type,
            )
        )
