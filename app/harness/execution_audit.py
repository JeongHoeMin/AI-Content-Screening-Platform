from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol, Tuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.article import Article
from app.workflows import ScreeningResult, ScreeningWorkflow, WorkflowContext, WorkflowStatistics


class ExecutionAuditStatus(str, Enum):
    """Terminal status captured for one workflow execution."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WorkflowExecutionAudit(BaseModel):
    """Safe, immutable execution summary suitable for operational audit storage."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    status: ExecutionAuditStatus
    started_at: datetime
    finished_at: datetime
    duration_seconds: float = Field(ge=0.0)
    input_article_count: int = Field(ge=0)
    statistics: Optional[WorkflowStatistics] = None
    error_type: Optional[str] = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_terminal_observation(self) -> "WorkflowExecutionAudit":
        if self.finished_at < self.started_at:
            raise ValueError("execution audit must not finish before it starts")
        if self.status is ExecutionAuditStatus.SUCCEEDED:
            if self.statistics is None or self.error_type is not None:
                raise ValueError("successful execution audit requires statistics and no error")
        elif self.statistics is not None or self.error_type is None:
            raise ValueError("failed execution audit requires an error type and no statistics")
        return self


class WorkflowExecutionAuditSink(Protocol):
    """Persistence boundary for safe workflow execution observations."""

    async def append(self, audit: WorkflowExecutionAudit) -> None:
        """Persist one terminal audit record."""


class JsonLinesWorkflowExecutionAuditSink:
    """Append execution audit records to an explicitly configured JSON Lines file."""

    def __init__(self, path: Path) -> None:
        self._path: Path = path

    async def append(self, audit: WorkflowExecutionAudit) -> None:
        await asyncio.to_thread(self._append_sync, audit)

    def _append_sync(self, audit: WorkflowExecutionAudit) -> None:
        serialized: str = json.dumps(audit.model_dump(mode="json"), ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as audit_file:
            audit_file.write(serialized)
            audit_file.write("\n")


Clock = Callable[[], datetime]
ExecutionIdFactory = Callable[[], str]


class ScreeningExecutionHarness:
    """Own workflow execution observation and optional audit persistence."""

    def __init__(
        self,
        audit_sink: Optional[WorkflowExecutionAuditSink] = None,
        clock: Clock = lambda: datetime.now(timezone.utc),
        execution_id_factory: ExecutionIdFactory = lambda: uuid4().hex,
    ) -> None:
        self._audit_sink: Optional[WorkflowExecutionAuditSink] = audit_sink
        self._clock: Clock = clock
        self._execution_id_factory: ExecutionIdFactory = execution_id_factory

    async def run(
        self,
        workflow: ScreeningWorkflow,
        articles: Tuple[Article, ...],
        execution_mode: str,
        context: Optional[WorkflowContext] = None,
    ) -> ScreeningResult:
        """Run one workflow and record its safe terminal observation when configured."""
        execution_id: str = self._execution_id_factory()
        started_at: datetime = self._clock()
        try:
            result: ScreeningResult
            if context is None:
                result = await workflow.run(articles)
            else:
                result = await workflow.run(articles, context)
        except Exception as error:
            finished_at: datetime = self._clock()
            failure: WorkflowExecutionAudit = WorkflowExecutionAudit(
                execution_id=execution_id,
                execution_mode=execution_mode,
                status=ExecutionAuditStatus.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=max(0.0, (finished_at - started_at).total_seconds()),
                input_article_count=len(articles),
                error_type=type(error).__name__,
            )
            await self._append(failure)
            raise
        finished_at = self._clock()
        success: WorkflowExecutionAudit = WorkflowExecutionAudit(
            execution_id=execution_id,
            execution_mode=execution_mode,
            status=ExecutionAuditStatus.SUCCEEDED,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=max(0.0, (finished_at - started_at).total_seconds()),
            input_article_count=len(articles),
            statistics=result.statistics,
        )
        await self._append(success)
        return result

    async def _append(self, audit: WorkflowExecutionAudit) -> None:
        if self._audit_sink is not None:
            await self._audit_sink.append(audit)
