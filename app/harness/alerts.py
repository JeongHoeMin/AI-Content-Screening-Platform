from __future__ import annotations

import asyncio
import json
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol, Tuple

import structlog
from pydantic import BaseModel, ConfigDict, Field

from app.harness.execution_audit import (
    WorkflowExecutionAudit,
    WorkflowExecutionAuditSink,
)

logger = structlog.get_logger(__name__)


class OperationalAlertSeverity(str, Enum):
    """Severity for an operational observation that needs human attention."""

    WARNING = "warning"
    CRITICAL = "critical"


class OperationalAlertType(str, Enum):
    """Closed v1 taxonomy for safe workflow operational alerts."""

    EXECUTION_FAILED = "execution_failed"
    DURATION_EXCEEDED = "duration_exceeded"


class OperationalAlert(BaseModel):
    """Immutable safe alert projection from one terminal execution audit."""

    model_config = ConfigDict(frozen=True)

    alert_id: str = Field(min_length=1)
    alert_type: OperationalAlertType
    severity: OperationalAlertSeverity
    execution_id: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    duration_seconds: float = Field(ge=0.0)
    input_article_count: int = Field(ge=0)
    error_type: Optional[str] = Field(default=None, min_length=1)
    duration_threshold_seconds: Optional[float] = Field(default=None, gt=0.0)


class OperationalAlertPolicyConfig(BaseModel):
    """Deterministic v1 thresholds for terminal workflow execution alerts."""

    model_config = ConfigDict(frozen=True)

    max_duration_seconds: Optional[float] = Field(default=None, gt=0.0)


class OperationalAlertPolicy:
    """Turn safe execution facts into alerts without changing workflow behavior."""

    def __init__(self, config: OperationalAlertPolicyConfig) -> None:
        self._config: OperationalAlertPolicyConfig = config

    def evaluate(self, audit: WorkflowExecutionAudit) -> Tuple[OperationalAlert, ...]:
        """Return every independently applicable v1 operational alert."""
        alerts: list[OperationalAlert] = []
        if audit.error_type is not None:
            alerts.append(
                OperationalAlert(
                    alert_id=f"{audit.execution_id}:execution_failed",
                    alert_type=OperationalAlertType.EXECUTION_FAILED,
                    severity=OperationalAlertSeverity.CRITICAL,
                    execution_id=audit.execution_id,
                    execution_mode=audit.execution_mode,
                    duration_seconds=audit.duration_seconds,
                    input_article_count=audit.input_article_count,
                    error_type=audit.error_type,
                )
            )
        threshold: Optional[float] = self._config.max_duration_seconds
        if threshold is not None and audit.duration_seconds > threshold:
            alerts.append(
                OperationalAlert(
                    alert_id=f"{audit.execution_id}:duration_exceeded",
                    alert_type=OperationalAlertType.DURATION_EXCEEDED,
                    severity=OperationalAlertSeverity.WARNING,
                    execution_id=audit.execution_id,
                    execution_mode=audit.execution_mode,
                    duration_seconds=audit.duration_seconds,
                    input_article_count=audit.input_article_count,
                    duration_threshold_seconds=threshold,
                )
            )
        return tuple(alerts)


class OperationalAlertSink(Protocol):
    """Best-effort delivery boundary for already-sanitized operational alerts."""

    async def deliver(self, alert: OperationalAlert) -> None:
        """Deliver one alert to an operational destination."""


class JsonLinesOperationalAlertSink:
    """Append safe alert payloads to an explicitly configured JSON Lines file."""

    def __init__(self, path: Path) -> None:
        self._path: Path = path

    async def deliver(self, alert: OperationalAlert) -> None:
        await asyncio.to_thread(self._deliver_sync, alert)

    def _deliver_sync(self, alert: OperationalAlert) -> None:
        serialized: str = json.dumps(alert.model_dump(mode="json"), ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as alert_file:
            alert_file.write(serialized)
            alert_file.write("\n")


class AlertingWorkflowExecutionAuditSink:
    """Persist audits first, then deliver any policy-derived alerts best-effort."""

    def __init__(
        self,
        audit_sink: WorkflowExecutionAuditSink,
        policy: OperationalAlertPolicy,
        alert_sink: OperationalAlertSink,
    ) -> None:
        self._audit_sink: WorkflowExecutionAuditSink = audit_sink
        self._policy: OperationalAlertPolicy = policy
        self._alert_sink: OperationalAlertSink = alert_sink

    async def append(self, audit: WorkflowExecutionAudit) -> None:
        await self._audit_sink.append(audit)
        alerts: Tuple[OperationalAlert, ...] = self._policy.evaluate(audit)
        for alert in alerts:
            try:
                await self._alert_sink.deliver(alert)
            except Exception as error:
                logger.error(
                    "operational_alert_delivery_failed",
                    alert_id=alert.alert_id,
                    error_type=type(error).__name__,
                )
