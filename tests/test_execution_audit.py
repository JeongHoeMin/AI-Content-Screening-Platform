from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional, Tuple

import pytest

from app.harness.execution_audit import (
    ExecutionAuditStatus,
    JsonLinesWorkflowExecutionAuditSink,
    ScreeningExecutionHarness,
    WorkflowExecutionAudit,
)
from app.models import Article
from app.workflows import ScreeningResult, WorkflowContext, WorkflowStatistics


def build_article() -> Article:
    return Article(
        id="article-1",
        title="Safe title",
        content="Safe content",
        source="example.com",
        published_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
        url="https://example.com/articles/1",
    )


def build_statistics() -> WorkflowStatistics:
    return WorkflowStatistics(
        total_articles=1,
        accepted_articles=1,
        rejected_articles=0,
        extracted_events=1,
        successful_batches=1,
        accepted_events=1,
        review_events=0,
        rejected_events=0,
        verified_events=0,
        partially_verified_events=0,
        conflicted_events=0,
        insufficient_evidence_events=0,
        resolved_accept_count=1,
        resolved_review_count=0,
        resolved_reject_count=0,
    )


class RecordingAuditSink:
    def __init__(self) -> None:
        self.audits: list[WorkflowExecutionAudit] = []

    async def append(self, audit: WorkflowExecutionAudit) -> None:
        self.audits.append(audit)


class SuccessfulWorkflow:
    def __init__(self, result: ScreeningResult) -> None:
        self.result: ScreeningResult = result
        self.received_context: Optional[WorkflowContext] = None

    async def run(
        self,
        articles: Tuple[Article, ...],
        context: Optional[WorkflowContext] = None,
    ) -> ScreeningResult:
        self.received_context = context
        return self.result


class FailingWorkflow:
    async def run(
        self,
        articles: Tuple[Article, ...],
        context: Optional[WorkflowContext] = None,
    ) -> ScreeningResult:
        raise RuntimeError("article content must not be persisted")


def build_result() -> ScreeningResult:
    return ScreeningResult.model_construct(statistics=build_statistics())


def build_clock() -> tuple[Callable[[], datetime], datetime]:
    started_at: datetime = datetime(2026, 7, 30, 0, 0, tzinfo=timezone.utc)
    timestamps: Iterator[datetime] = iter(
        (started_at, started_at + timedelta(seconds=1.25))
    )

    def clock() -> datetime:
        return next(timestamps)

    return clock, started_at


@pytest.mark.anyio
async def test_screening_execution_harness_records_safe_success_observation() -> None:
    clock, started_at = build_clock()
    sink: RecordingAuditSink = RecordingAuditSink()
    workflow: SuccessfulWorkflow = SuccessfulWorkflow(build_result())
    harness: ScreeningExecutionHarness = ScreeningExecutionHarness(
        audit_sink=sink,
        clock=clock,
        execution_id_factory=lambda: "execution-123",
    )

    result: ScreeningResult = await harness.run(
        workflow,
        (build_article(),),
        execution_mode="mock",
    )

    assert result.statistics == build_statistics()
    assert len(sink.audits) == 1
    audit: WorkflowExecutionAudit = sink.audits[0]
    assert audit.execution_id == "execution-123"
    assert audit.execution_mode == "mock"
    assert audit.status is ExecutionAuditStatus.SUCCEEDED
    assert audit.started_at == started_at
    assert audit.duration_seconds == 1.25
    assert audit.input_article_count == 1
    assert audit.statistics == build_statistics()
    assert audit.error_type is None


@pytest.mark.anyio
async def test_screening_execution_harness_records_only_error_type_for_failure() -> None:
    clock, _ = build_clock()
    sink: RecordingAuditSink = RecordingAuditSink()
    harness: ScreeningExecutionHarness = ScreeningExecutionHarness(
        audit_sink=sink,
        clock=clock,
        execution_id_factory=lambda: "execution-456",
    )

    with pytest.raises(RuntimeError, match="article content"):
        await harness.run(FailingWorkflow(), (build_article(),), execution_mode="openai")

    assert len(sink.audits) == 1
    audit: WorkflowExecutionAudit = sink.audits[0]
    assert audit.status is ExecutionAuditStatus.FAILED
    assert audit.statistics is None
    assert audit.error_type == "RuntimeError"
    assert "article content" not in audit.model_dump_json()


@pytest.mark.anyio
async def test_json_lines_audit_sink_appends_one_safe_json_object_per_execution(
    tmp_path: Path,
) -> None:
    audit_path: Path = tmp_path / "execution-audit.jsonl"
    sink: JsonLinesWorkflowExecutionAuditSink = JsonLinesWorkflowExecutionAuditSink(audit_path)
    timestamp: datetime = datetime(2026, 7, 30, tzinfo=timezone.utc)
    audit: WorkflowExecutionAudit = WorkflowExecutionAudit(
        execution_id="execution-789",
        execution_mode="mock",
        status=ExecutionAuditStatus.SUCCEEDED,
        started_at=timestamp,
        finished_at=timestamp,
        duration_seconds=0.0,
        input_article_count=0,
        statistics=build_statistics().model_copy(update={"total_articles": 0, "accepted_articles": 0, "extracted_events": 0, "successful_batches": 0, "accepted_events": 0, "resolved_accept_count": 0}),
    )

    await sink.append(audit)

    lines: list[str] = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload: dict[str, object] = json.loads(lines[0])
    assert payload["execution_id"] == "execution-789"
    assert payload["status"] == "succeeded"
    assert "title" not in payload
    assert "content" not in payload
