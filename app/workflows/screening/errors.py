"""Safe terminal workflow errors for exhausted LLM retry stages."""

from __future__ import annotations


class WorkflowStageRetriesExhaustedError(RuntimeError):
    """Raised after the configured attempts for one retryable LLM stage fail."""

    def __init__(self, stage: str, error_type: str, attempts: int = 3) -> None:
        self.stage: str = stage
        self.error_type: str = error_type
        self.attempts: int = attempts
        super().__init__(f"{stage} retries exhausted: {error_type}")
