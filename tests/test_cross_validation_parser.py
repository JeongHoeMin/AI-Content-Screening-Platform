from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.cross_validators import DefaultCrossValidationAssessmentParser
from app.models import CrossValidationAssessmentResponse, CrossValidationAssessmentResponseItem, CrossValidationEvidenceResponseItem, CrossValidationParseErrorKind
from tests.test_cross_validation_policy import article, candidate


def item(event_index: object, evidence: list[CrossValidationEvidenceResponseItem]) -> CrossValidationAssessmentResponseItem:
    return CrossValidationAssessmentResponseItem(event_index=event_index, confidence=80, reasons=["Compared."], evidence=evidence)


def evidence(index: object, relation: object = "supports", matched: list[object] | None = None, conflicting: list[object] | None = None) -> CrossValidationEvidenceResponseItem:
    return CrossValidationEvidenceResponseItem(evidence_index=index, relation=relation, matched_claims=matched if matched is not None else ["Match"], conflicting_claims=conflicting if conflicting is not None else [])


def test_parser_preserves_valid_sibling_and_evidence_identity() -> None:
    candidates = (candidate((article("a", "Reuters"), article("b", "Bloomberg"))), candidate((article("c", "AP"),)))
    response = CrossValidationAssessmentResponse(assessments=[item(1, [evidence(0)]), item(0, [evidence(0), evidence("bad")])])
    parsed = DefaultCrossValidationAssessmentParser().parse(response, candidates)
    assert tuple(value.candidate_id for value in parsed.assessments) == ("source:0", "source:0")
    assert parsed.assessments[0].evidence[0].article_id == "a"
    assert any(error.kind is CrossValidationParseErrorKind.INVALID_EVIDENCE_INDEX for error in parsed.errors)


@pytest.mark.parametrize("index", ["1", True, None, -1, 2])
def test_parser_records_invalid_event_index(index: object) -> None:
    candidates = (candidate((article("a", "Reuters"),)),)
    parsed = DefaultCrossValidationAssessmentParser().parse(CrossValidationAssessmentResponse(assessments=[item(index, [evidence(0)])]), candidates)
    assert any(error.kind is CrossValidationParseErrorKind.INVALID_EVENT_INDEX for error in parsed.errors)


@pytest.mark.parametrize("relation", ["support", "verified", 1, True, None])
def test_parser_rejects_invalid_relation_without_other_evidence_loss(relation: object) -> None:
    candidates = (candidate((article("a", "Reuters"), article("b", "Bloomberg"))),)
    parsed = DefaultCrossValidationAssessmentParser().parse(CrossValidationAssessmentResponse(assessments=[item(0, [evidence(0), evidence(1, relation=relation)])]), candidates)
    assert len(parsed.assessments) == 1
    assert len(parsed.assessments[0].evidence) == 1
    assert any(error.kind is CrossValidationParseErrorKind.INVALID_RELATION for error in parsed.errors)


def test_response_rejects_extra_property_and_root_error() -> None:
    with pytest.raises(ValidationError):
        CrossValidationAssessmentResponse.model_validate({"assessments": {}})
    with pytest.raises(ValidationError):
        CrossValidationEvidenceResponseItem.model_validate({"evidence_index": 0, "relation": "supports", "extra": True})
