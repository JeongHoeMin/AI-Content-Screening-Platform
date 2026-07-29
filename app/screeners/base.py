from __future__ import annotations

from typing import Protocol, Tuple

from app.models.llm_inference import LLMInferenceResult
from app.models.screening import ScreeningDecision


class EventScreener(Protocol):
    """Creates ordered final screening decisions for extracted event snapshots."""

    async def screen(
        self,
        inferences: Tuple[LLMInferenceResult, ...],
    ) -> Tuple[ScreeningDecision, ...]:
        """Return policy decisions while retaining input NewsEvent identity."""
        ...
