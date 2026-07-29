from __future__ import annotations

from typing import Dict, Set, Tuple

from app.models.screening import (
    ScreeningAssessment,
    ScreeningAssessmentResponse,
    ScreeningCandidate,
)
from app.screeners.errors import ScreeningAssessmentValidationError
from app.screeners.parser import ScreeningAssessmentParser


class DefaultScreeningAssessmentParser(ScreeningAssessmentParser):
    """Matches typed assessment IDs to candidates without changing their order."""

    def parse(
        self,
        response: ScreeningAssessmentResponse,
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> Tuple[ScreeningAssessment, ...]:
        candidates_by_id: Dict[str, ScreeningCandidate] = self._index_candidates(
            candidates
        )
        assessments_by_id: Dict[str, ScreeningAssessment] = self._index_assessments(
            response.assessments
        )
        self._validate_matching_ids(candidates_by_id, assessments_by_id)
        return tuple(
            assessments_by_id[candidate.candidate_id] for candidate in candidates
        )

    @staticmethod
    def _index_candidates(
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> Dict[str, ScreeningCandidate]:
        candidates_by_id: Dict[str, ScreeningCandidate] = {
            candidate.candidate_id: candidate for candidate in candidates
        }
        if len(candidates_by_id) != len(candidates):
            raise ScreeningAssessmentValidationError(
                "Input screening candidates contain duplicate IDs"
            )
        return candidates_by_id

    @staticmethod
    def _index_assessments(
        assessments: Tuple[ScreeningAssessment, ...],
    ) -> Dict[str, ScreeningAssessment]:
        assessments_by_id: Dict[str, ScreeningAssessment] = {
            assessment.candidate_id: assessment for assessment in assessments
        }
        if len(assessments_by_id) != len(assessments):
            raise ScreeningAssessmentValidationError(
                "LLM output contains duplicate screening candidate IDs"
            )
        return assessments_by_id

    @staticmethod
    def _validate_matching_ids(
        candidates_by_id: Dict[str, ScreeningCandidate],
        assessments_by_id: Dict[str, ScreeningAssessment],
    ) -> None:
        candidate_ids: Set[str] = set(candidates_by_id)
        assessment_ids: Set[str] = set(assessments_by_id)
        missing_ids: Set[str] = candidate_ids - assessment_ids
        unknown_ids: Set[str] = assessment_ids - candidate_ids
        if missing_ids or unknown_ids:
            raise ScreeningAssessmentValidationError(
                "LLM assessment IDs do not match input screening candidate IDs: "
                f"missing={sorted(missing_ids)}, unknown={sorted(unknown_ids)}"
            )
