from __future__ import annotations


class InferenceResultValidationError(ValueError):
    """Raised when LLM inference output does not match its input articles."""


class AllExtractionBatchesFailedError(RuntimeError):
    """Raised when every attempted extraction batch fails recoverably."""

    def __init__(self, error_type: str = "UnknownError") -> None:
        self.error_type: str = error_type
        super().__init__("All OpenAI extraction batches failed")
