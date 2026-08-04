from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional, Tuple

import pytest

from app.harness.execution_audit import (
    ExecutionAuditStatus,
    JsonLinesWorkflowExecutionAuditSink,
    JsonLinesWorkflowExecutionAuditReader,
    ScreeningExecutionHarness,
    WorkflowAuditReadError,
    WorkflowExecutionAudit,
    calculate_workflow_execution_metrics,
)
from app.models import Article
from app.workflows import ScreeningResult, WorkflowContext, WorkflowStatistics


class RecordingDocumentPersistence:
    def __init__(self) -> None:
        self.calls: list[Tuple[Article, ...]] = []

    async def persist(self, articles: Tuple[Article, ...]) -> None:
        self.calls.append(articles)


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


class RecordingAuditPersistence:
    def __init__(self) -> None:
        self.audits: list[WorkflowExecutionAudit] = []

    async def persist(self, audit: WorkflowExecutionAudit) -> None:
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
async def test_screening_execution_harness_persists_the_same_safe_terminal_audit() -> None:
    clock, _ = build_clock()
    persistence: RecordingAuditPersistence = RecordingAuditPersistence()
    harness: ScreeningExecutionHarness = ScreeningExecutionHarness(
        clock=clock,
        execution_id_factory=lambda: "execution-persisted",
        execution_audit_persistence=persistence,
    )

    await harness.run(SuccessfulWorkflow(build_result()), (build_article(),), execution_mode="mock")

    assert len(persistence.audits) == 1
    audit: WorkflowExecutionAudit = persistence.audits[0]
    assert audit.execution_id == "execution-persisted"
    assert audit.statistics == build_statistics()
    assert "content" not in audit.model_dump(mode="json")
    assert "url" not in audit.model_dump(mode="json")


@pytest.mark.anyio
async def test_screening_execution_harness_owns_document_persistence() -> None:
    clock, _ = build_clock()
    persistence = RecordingDocumentPersistence()
    article = build_article()
    harness = ScreeningExecutionHarness(
        clock=clock,
        document_persistence=persistence,
    )

    await harness.run(SuccessfulWorkflow(build_result()), (article,), execution_mode="mock")

    assert persistence.calls == [(article,)]


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


@pytest.mark.anyio
async def test_json_lines_audit_reader_rejects_malformed_record_without_skipping_it(
    tmp_path: Path,
) -> None:
    audit_path: Path = tmp_path / "invalid-audit.jsonl"
    audit_path.write_text("{not-json}\n", encoding="utf-8")

    with pytest.raises(WorkflowAuditReadError, match="line 1"):
        await JsonLinesWorkflowExecutionAuditReader(audit_path).read()


def test_execution_metrics_aggregate_safe_success_and_failure_observations() -> None:
    timestamp: datetime = datetime(2026, 7, 30, tzinfo=timezone.utc)
    success: WorkflowExecutionAudit = WorkflowExecutionAudit(
        execution_id="success",
        execution_mode="mock",
        status=ExecutionAuditStatus.SUCCEEDED,
        started_at=timestamp,
        finished_at=timestamp + timedelta(seconds=2),
        duration_seconds=2.0,
        input_article_count=3,
        statistics=build_statistics(),
    )
    failure: WorkflowExecutionAudit = WorkflowExecutionAudit(
        execution_id="failure",
        execution_mode="openai",
        status=ExecutionAuditStatus.FAILED,
        started_at=timestamp,
        finished_at=timestamp + timedelta(seconds=4),
        duration_seconds=4.0,
        input_article_count=2,
        error_type="RuntimeError",
    )

    metrics = calculate_workflow_execution_metrics((success, failure))

    assert metrics.total_executions == 2
    assert metrics.succeeded_executions == 1
    assert metrics.failed_executions == 1
    assert metrics.total_duration_seconds == 6.0
    assert metrics.average_duration_seconds == 3.0
    assert metrics.total_input_articles == 5
    assert metrics.total_accepted_events == 1
    assert metrics.total_resolved_accepts == 1
