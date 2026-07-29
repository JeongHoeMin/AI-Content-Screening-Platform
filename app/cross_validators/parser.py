from __future__ import annotations

from typing import Protocol, Tuple

from app.models.cross_validation import (
    CrossValidationAssessment,
    CrossValidationAssessmentResponse,
    CrossValidationCandidate,
)


class CrossValidationAssessmentParser(Protocol):
    def parse(
        self,
        response: CrossValidationAssessmentResponse,
        candidates: Tuple[CrossValidationCandidate, ...],
    ) -> Tuple[CrossValidationAssessment, ...]:
        ...
