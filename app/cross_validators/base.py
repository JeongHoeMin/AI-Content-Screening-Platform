from __future__ import annotations

from typing import Protocol, Tuple

from app.models.cross_validation import CrossValidationCandidate, CrossValidationResult


class CrossValidator(Protocol):
    async def validate(
        self, candidates: Tuple[CrossValidationCandidate, ...]
    ) -> Tuple[CrossValidationResult, ...]:
        ...
