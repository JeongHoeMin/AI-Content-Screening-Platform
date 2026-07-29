from __future__ import annotations


class InferenceResultValidationError(ValueError):
    """Raised when LLM inference output does not match its input articles."""
