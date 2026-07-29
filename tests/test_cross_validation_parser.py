from __future__ import annotations

from typing import Tuple

import pytest

from app.cross_validators import (
    CrossValidationAssessmentValidationError,
    DefaultCrossValidationAssessmentParser,
)
from app.models import CrossValidationAssessment, CrossValidationAssessmentResponse, CrossValidationCandidate
from tests.test_cross_validation_policy import article, candidate


def assessment(candidate_id: str, **values: object) -> CrossValidationAssessment:
    return CrossValidationAssessment(candidate_id=candidate_id, confidence=70, reasons=("Compared.",), **values)


def parser() -> DefaultCrossValidationAssessmentParser:
    return DefaultCrossValidationAssessmentParser()


def test_parser_restores_candidate_order() -> None:
    first: CrossValidationCandidate = candidate((article("a", "Reuters"),))
    second: CrossValidationCandidate = first.model_copy(update={"candidate_id": "source:1"})
    result = parser().parse(CrossValidationAssessmentResponse(assessments=(assessment("source:1"), assessment("source:0"))), (first, second))
    assert tuple(item.candidate_id for item in result) == ("source:0", "source:1")


@pytest.mark.parametrize(
    "response,candidates",
    [
        (CrossValidationAssessmentResponse(assessments=(assessment("source:0"),)), (candidate(()), candidate(()))),
        (CrossValidationAssessmentResponse(assessments=(assessment("unknown"),)), (candidate(()),)),
        (CrossValidationAssessmentResponse(assessments=(assessment("source:0"), assessment("source:0"))), (candidate(()),)),
        (CrossValidationAssessmentResponse(assessments=(assessment("source:0"),)), (candidate(()).model_copy(update={"candidate_id": "duplicate"}), candidate(()).model_copy(update={"candidate_id": "duplicate"}))),
    ],
)
def test_parser_rejects_candidate_id_contract_violations(response: CrossValidationAssessmentResponse, candidates: Tuple[CrossValidationCandidate, ...]) -> None:
    with pytest.raises(CrossValidationAssessmentValidationError):
        parser().parse(response, candidates)


@pytest.mark.parametrize(
    "values",
    [
        {"supporting_article_ids": ("a", "a")},
        {"supporting_article_ids": ("a",), "partially_matching_article_ids": ("a",)},
        {"supporting_article_ids": ("unknown",)},
        {"contradicting_article_ids": ("source",)},
    ],
)
def test_parser_rejects_invalid_evidence_article_references(values: dict[str, object]) -> None:
    item: CrossValidationCandidate = candidate((article("a", "Reuters"),))
    response = CrossValidationAssessmentResponse(assessments=(assessment("source:0", **values),))
    with pytest.raises(CrossValidationAssessmentValidationError):
        parser().parse(response, (item,))
