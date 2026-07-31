"""Safe structured application logging for long-running web executions."""

from __future__ import annotations

import os
import logging
from pathlib import Path

import structlog


def configure_application_logging() -> None:
    """Append JSON logs to the configured local runtime path when available."""
    raw_path: str = os.getenv("APP_LOG_PATH", "").strip()
    if not raw_path:
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        )
        return
    path: Path = Path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    log_file = path.open("a", encoding="utf-8")
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.WriteLoggerFactory(file=log_file),
    )
