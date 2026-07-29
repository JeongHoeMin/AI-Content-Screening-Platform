from __future__ import annotations

from typing import Dict, Set, Tuple

from app.cross_validators.errors import CrossValidationAssessmentValidationError
from app.cross_validators.parser import CrossValidationAssessmentParser
from app.models.cross_validation import (
    CrossValidationAssessment,
    CrossValidationAssessmentResponse,
    CrossValidationCandidate,
)


class DefaultCrossValidationAssessmentParser(CrossValidationAssessmentParser):
    def parse(self, response: CrossValidationAssessmentResponse, candidates: Tuple[CrossValidationCandidate, ...]) -> Tuple[CrossValidationAssessment, ...]:
        candidate_map: Dict[str, CrossValidationCandidate] = {candidate.candidate_id: candidate for candidate in candidates}
        assessment_map: Dict[str, CrossValidationAssessment] = {assessment.candidate_id: assessment for assessment in response.assessments}
        if len(candidate_map) != len(candidates):
            raise CrossValidationAssessmentValidationError("Input cross validation candidates contain duplicate IDs")
        if len(assessment_map) != len(response.assessments):
            raise CrossValidationAssessmentValidationError("LLM output contains duplicate cross validation candidate IDs")
        if set(candidate_map) != set(assessment_map):
            raise CrossValidationAssessmentValidationError("LLM assessment IDs do not match input cross validation candidate IDs")
        for candidate in candidates:
            self._validate_article_ids(assessment_map[candidate.candidate_id], candidate)
        return tuple(assessment_map[candidate.candidate_id] for candidate in candidates)

    @staticmethod
    def _validate_article_ids(assessment: CrossValidationAssessment, candidate: CrossValidationCandidate) -> None:
        groups: Tuple[Tuple[str, ...], ...] = (assessment.supporting_article_ids, assessment.partially_matching_article_ids, assessment.contradicting_article_ids)
        ids: Tuple[str, ...] = tuple(article_id for group in groups for article_id in group)
        if len(set(ids)) != len(ids):
            raise CrossValidationAssessmentValidationError("Evidence article IDs must be unique across relations")
        related_ids: Set[str] = {article.id for article in candidate.related_articles}
        if candidate.source_article.id in ids:
            raise CrossValidationAssessmentValidationError("Source article ID cannot be returned as evidence")
        if not set(ids).issubset(related_ids):
            raise CrossValidationAssessmentValidationError("LLM output contains unknown related article IDs")
