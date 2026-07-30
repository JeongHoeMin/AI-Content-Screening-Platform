from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol, Sequence, Tuple
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


class WorkflowAuditReadError(ValueError):
    """Raised when persisted workflow audit data is absent or invalid."""


class WorkflowExecutionMetrics(BaseModel):
    """Immutable aggregate of safe terminal workflow execution observations."""

    model_config = ConfigDict(frozen=True)

    total_executions: int = Field(ge=0)
    succeeded_executions: int = Field(ge=0)
    failed_executions: int = Field(ge=0)
    total_duration_seconds: float = Field(ge=0.0)
    average_duration_seconds: float = Field(ge=0.0)
    total_input_articles: int = Field(ge=0)
    total_accepted_events: int = Field(ge=0)
    total_review_events: int = Field(ge=0)
    total_rejected_events: int = Field(ge=0)
    total_resolved_accepts: int = Field(ge=0)
    total_resolved_reviews: int = Field(ge=0)
    total_resolved_rejects: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_execution_totals(self) -> "WorkflowExecutionMetrics":
        if self.succeeded_executions + self.failed_executions != self.total_executions:
            raise ValueError("execution status counts must equal total executions")
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


class JsonLinesWorkflowExecutionAuditReader:
    """Load validated execution audit records from one JSON Lines file."""

    def __init__(self, path: Path) -> None:
        self._path: Path = path

    async def read(self) -> Tuple[WorkflowExecutionAudit, ...]:
        return await asyncio.to_thread(self._read_sync)

    def _read_sync(self) -> Tuple[WorkflowExecutionAudit, ...]:
        try:
            lines: list[str] = self._path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise WorkflowAuditReadError("Unable to read workflow audit log") from error
        audits: list[WorkflowExecutionAudit] = []
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                raise WorkflowAuditReadError(
                    f"Workflow audit log contains an empty record at line {line_number}"
                )
            try:
                payload: object = json.loads(line)
                audit: WorkflowExecutionAudit = WorkflowExecutionAudit.model_validate(payload)
            except (json.JSONDecodeError, ValueError) as error:
                raise WorkflowAuditReadError(
                    f"Workflow audit log contains an invalid record at line {line_number}"
                ) from error
            audits.append(audit)
        return tuple(audits)


def calculate_workflow_execution_metrics(
    audits: Sequence[WorkflowExecutionAudit],
) -> WorkflowExecutionMetrics:
    """Calculate deterministic operational metrics without changing workflow decisions."""
    total_executions: int = len(audits)
    succeeded_executions: int = sum(
        audit.status is ExecutionAuditStatus.SUCCEEDED for audit in audits
    )
    total_duration_seconds: float = sum(audit.duration_seconds for audit in audits)
    total_input_articles: int = sum(audit.input_article_count for audit in audits)
    successful_statistics: list[WorkflowStatistics] = [
        audit.statistics
        for audit in audits
        if audit.statistics is not None
    ]
    return WorkflowExecutionMetrics(
        total_executions=total_executions,
        succeeded_executions=succeeded_executions,
        failed_executions=total_executions - succeeded_executions,
        total_duration_seconds=total_duration_seconds,
        average_duration_seconds=(
            total_duration_seconds / total_executions if total_executions else 0.0
        ),
        total_input_articles=total_input_articles,
        total_accepted_events=sum(
            statistics.accepted_events for statistics in successful_statistics
        ),
        total_review_events=sum(
            statistics.review_events for statistics in successful_statistics
        ),
        total_rejected_events=sum(
            statistics.rejected_events for statistics in successful_statistics
        ),
        total_resolved_accepts=sum(
            statistics.resolved_accept_count for statistics in successful_statistics
        ),
        total_resolved_reviews=sum(
            statistics.resolved_review_count for statistics in successful_statistics
        ),
        total_resolved_rejects=sum(
            statistics.resolved_reject_count for statistics in successful_statistics
        ),
    )


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
            request_budget = getattr(workflow, "request_budget", None)
            if request_budget is None:
                if context is None:
                    result = await workflow.run(articles)
                else:
                    result = await workflow.run(articles, context)
            else:
                with request_budget.execution_scope():
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
