from __future__ import annotations


class StructuredOutputCallError(RuntimeError):
    """Raised when a structured-output provider call fails."""

    def __init__(self, provider: str, error_type: str) -> None:
        self.provider: str = provider
        self.error_type: str = error_type
        super().__init__(f"{provider} structured output request failed: {error_type}")


class StructuredOutputResponseError(ValueError):
    """Raised when a provider response cannot produce structured output."""

    def __init__(self, reason: str) -> None:
        self.reason: str = reason
        super().__init__(f"Structured output response failed: {reason}")
