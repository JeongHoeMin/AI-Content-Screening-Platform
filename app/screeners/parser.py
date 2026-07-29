from __future__ import annotations

from typing import Protocol, Tuple

from app.models.screening import (
    ScreeningAssessment,
    ScreeningAssessmentResponse,
    ScreeningCandidate,
)


class ScreeningAssessmentParser(Protocol):
    """Validates typed assessment output and restores input candidate order."""

    def parse(
        self,
        response: ScreeningAssessmentResponse,
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> Tuple[ScreeningAssessment, ...]:
        """Return exactly one matching assessment for every candidate in order."""
        ...
