from __future__ import annotations

from typing import Protocol, Tuple

from app.models.cross_validation import (
    CrossValidationAssessmentResponse,
    CrossValidationCandidate,
    CrossValidationParseResult,
)


class CrossValidationAssessmentParser(Protocol):
    def parse(
        self,
        response: CrossValidationAssessmentResponse,
        candidates: Tuple[CrossValidationCandidate, ...],
    ) -> CrossValidationParseResult:
        ...
