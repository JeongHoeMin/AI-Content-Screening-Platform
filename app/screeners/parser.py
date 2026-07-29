from __future__ import annotations

from typing import Protocol, Tuple

from app.models.screening import (
    ScreeningAssessmentResponse,
    ScreeningCandidate,
    ScreeningParseResult,
)


class ScreeningAssessmentParser(Protocol):
    """Validates typed assessment output and restores input candidate order."""

    def parse(
        self,
        response: ScreeningAssessmentResponse,
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> ScreeningParseResult:
        """Return valid ordered assessments and safe per-candidate observations."""
        ...
