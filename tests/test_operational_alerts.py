from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.harness.alerts import (
    AlertingWorkflowExecutionAuditSink,
    OperationalAlertPolicy,
    OperationalAlertPolicyConfig,
    OperationalAlertSeverity,
    OperationalAlertType,
)
from app.harness.execution_audit import ExecutionAuditStatus, WorkflowExecutionAudit


def build_failed_audit(duration_seconds: float = 3.0) -> WorkflowExecutionAudit:
    timestamp: datetime = datetime(2026, 7, 30, tzinfo=timezone.utc)
    return WorkflowExecutionAudit(
        execution_id="execution-1",
        execution_mode="mock",
        status=ExecutionAuditStatus.FAILED,
        started_at=timestamp,
        finished_at=timestamp,
        duration_seconds=duration_seconds,
        input_article_count=2,
        error_type="RuntimeError",
    )


def test_alert_policy_preserves_independent_failure_and_duration_alerts() -> None:
    policy: OperationalAlertPolicy = OperationalAlertPolicy(
        OperationalAlertPolicyConfig(max_duration_seconds=2.0)
    )

    alerts = policy.evaluate(build_failed_audit())

    assert [alert.alert_type for alert in alerts] == [
        OperationalAlertType.EXECUTION_FAILED,
        OperationalAlertType.DURATION_EXCEEDED,
    ]
    assert alerts[0].severity is OperationalAlertSeverity.CRITICAL
    assert alerts[0].error_type == "RuntimeError"
    assert alerts[1].severity is OperationalAlertSeverity.WARNING
    assert alerts[1].duration_threshold_seconds == 2.0
    assert alerts[1].error_type is None


@pytest.mark.anyio
async def test_alerting_audit_sink_persists_before_best_effort_delivery_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    log_events: list[dict[str, object]] = []

    class AuditSink:
        async def append(self, audit: WorkflowExecutionAudit) -> None:
            events.append("audit")

    class FailingAlertSink:
        async def deliver(self, alert: object) -> None:
            events.append("alert")
            raise RuntimeError("sensitive delivery detail")

    class Logger:
        def error(self, event: str, **kwargs: object) -> None:
            log_events.append({"event": event, **kwargs})

    monkeypatch.setattr("app.harness.alerts.logger", Logger())
    sink: AlertingWorkflowExecutionAuditSink = AlertingWorkflowExecutionAuditSink(
        audit_sink=AuditSink(),
        policy=OperationalAlertPolicy(OperationalAlertPolicyConfig()),
        alert_sink=FailingAlertSink(),
    )

    await sink.append(build_failed_audit())

    assert events == ["audit", "alert"]
    assert log_events == [
        {
            "event": "operational_alert_delivery_failed",
            "alert_id": "execution-1:execution_failed",
            "error_type": "RuntimeError",
        }
    ]
