from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Set, Tuple

from pydantic import ValidationError

from app.cross_validators.parser import CrossValidationAssessmentParser
from app.models.cross_validation import (
    CrossValidationAssessment,
    CrossValidationAssessmentEvidence,
    CrossValidationAssessmentResponse,
    CrossValidationAssessmentResponseItem,
    CrossValidationCandidate,
    CrossValidationEvidenceResponseItem,
    CrossValidationParseError,
    CrossValidationParseErrorKind,
    CrossValidationParseResult,
    EvidenceRelation,
)


class DefaultCrossValidationAssessmentParser(CrossValidationAssessmentParser):
    """Restores valid evidence by local indexes without losing sibling events."""

    def parse(
        self,
        response: CrossValidationAssessmentResponse,
        candidates: Tuple[CrossValidationCandidate, ...],
    ) -> CrossValidationParseResult:
        errors: List[CrossValidationParseError] = []
        indexed_items: List[tuple[int, CrossValidationAssessmentResponseItem]] = []
        for item in response.assessments:
            try:
                event_index: int = self._parse_index(item.event_index)
            except ValueError:
                errors.append(self._error(CrossValidationParseErrorKind.INVALID_EVENT_INDEX))
                continue
            indexed_items.append((event_index, item))
        valid_indexes: Set[int] = set(range(len(candidates)))
        duplicate_indexes: Set[int] = {
            index for index, count in Counter(index for index, _ in indexed_items).items() if count > 1
        }
        assessments_by_index: Dict[int, CrossValidationAssessment] = {}
        invalid_indexes: Set[int] = set()
        for event_index, item in indexed_items:
            if event_index not in valid_indexes:
                errors.append(self._error(CrossValidationParseErrorKind.INVALID_EVENT_INDEX, event_index=event_index))
                continue
            if event_index in duplicate_indexes:
                invalid_indexes.add(event_index)
                continue
            assessment, item_errors = self._map_assessment(item, event_index, candidates)
            errors.extend(item_errors)
            if assessment is None:
                invalid_indexes.add(event_index)
            else:
                assessments_by_index[event_index] = assessment
        for event_index in sorted(duplicate_indexes & valid_indexes):
            errors.append(self._error_for_candidate(CrossValidationParseErrorKind.DUPLICATE_EVENT_INDEX, event_index, candidates))
        for event_index in range(len(candidates)):
            if event_index not in assessments_by_index and event_index not in invalid_indexes:
                errors.append(self._error_for_candidate(CrossValidationParseErrorKind.MISSING_EVENT_INDEX, event_index, candidates))
        return CrossValidationParseResult(
            assessments=tuple(assessments_by_index[index] for index in range(len(candidates)) if index in assessments_by_index),
            errors=tuple(errors),
        )

    def _map_assessment(
        self,
        item: CrossValidationAssessmentResponseItem,
        event_index: int,
        candidates: Tuple[CrossValidationCandidate, ...],
    ) -> tuple[CrossValidationAssessment | None, Tuple[CrossValidationParseError, ...]]:
        candidate: CrossValidationCandidate = candidates[event_index]
        errors: List[CrossValidationParseError] = []
        try:
            confidence: int = self._parse_score(item.confidence)
        except ValueError:
            return None, (self._error_for_candidate(CrossValidationParseErrorKind.INVALID_CONFIDENCE, event_index, candidates),)
        try:
            reasons: Tuple[str, ...] = self._normalize_strings(item.reasons, maximum=3, required=True)
        except ValueError:
            return None, (self._error_for_candidate(CrossValidationParseErrorKind.INVALID_REASONS, event_index, candidates),)
        evidence_by_index, evidence_errors = self._map_evidence(item.evidence, event_index, candidate)
        errors.extend(evidence_errors)
        if not evidence_by_index:
            return None, tuple(errors)
        try:
            assessment: CrossValidationAssessment = CrossValidationAssessment(
                candidate_id=candidate.candidate_id,
                confidence=confidence,
                evidence=tuple(evidence_by_index[index] for index in sorted(evidence_by_index)),
                reasons=reasons,
            )
        except ValidationError:
            errors.append(self._error_for_candidate(CrossValidationParseErrorKind.DOMAIN_CONVERSION, event_index, (candidate,)))
            return None, tuple(errors)
        return assessment, tuple(errors)

    def _map_evidence(
        self,
        items: List[CrossValidationEvidenceResponseItem],
        event_index: int,
        candidate: CrossValidationCandidate,
    ) -> tuple[Dict[int, CrossValidationAssessmentEvidence], Tuple[CrossValidationParseError, ...]]:
        errors: List[CrossValidationParseError] = []
        indexed_items: List[tuple[int, CrossValidationEvidenceResponseItem]] = []
        for item in items:
            try:
                evidence_index: int = self._parse_index(item.evidence_index)
            except ValueError:
                errors.append(self._error(CrossValidationParseErrorKind.INVALID_EVIDENCE_INDEX, event_index=event_index, candidate_id=candidate.candidate_id))
                continue
            indexed_items.append((evidence_index, item))
        valid_indexes: Set[int] = set(range(len(candidate.related_articles)))
        duplicate_indexes: Set[int] = {index for index, count in Counter(index for index, _ in indexed_items).items() if count > 1}
        evidence_by_index: Dict[int, CrossValidationAssessmentEvidence] = {}
        for evidence_index, item in indexed_items:
            article_id: str | None = candidate.related_articles[evidence_index].id if evidence_index in valid_indexes else None
            if evidence_index not in valid_indexes:
                errors.append(self._error(CrossValidationParseErrorKind.INVALID_EVIDENCE_INDEX, event_index=event_index, evidence_index=evidence_index, candidate_id=candidate.candidate_id))
                continue
            if evidence_index in duplicate_indexes:
                continue
            evidence, evidence_errors = self._map_evidence_item(item, event_index, evidence_index, candidate)
            errors.extend(evidence_errors)
            if evidence is not None:
                evidence_by_index[evidence_index] = evidence
        for evidence_index in sorted(duplicate_indexes & valid_indexes):
            errors.append(self._error(CrossValidationParseErrorKind.DUPLICATE_EVIDENCE_INDEX, event_index=event_index, evidence_index=evidence_index, candidate_id=candidate.candidate_id, article_id=candidate.related_articles[evidence_index].id))
        return evidence_by_index, tuple(errors)

    def _map_evidence_item(self, item: CrossValidationEvidenceResponseItem, event_index: int, evidence_index: int, candidate: CrossValidationCandidate) -> tuple[CrossValidationAssessmentEvidence | None, Tuple[CrossValidationParseError, ...]]:
        article_id: str = candidate.related_articles[evidence_index].id
        common: dict[str, object] = {"event_index": event_index, "evidence_index": evidence_index, "candidate_id": candidate.candidate_id, "article_id": article_id}
        try:
            relation: EvidenceRelation = self._parse_relation(item.relation)
        except ValueError:
            return None, (self._error(CrossValidationParseErrorKind.INVALID_RELATION, **common),)
        try:
            matched_claims: Tuple[str, ...] = self._normalize_strings(item.matched_claims, maximum=3, required=False)
        except ValueError:
            return None, (self._error(CrossValidationParseErrorKind.INVALID_MATCHED_CLAIMS, **common),)
        try:
            conflicting_claims: Tuple[str, ...] = self._normalize_strings(item.conflicting_claims, maximum=3, required=False)
        except ValueError:
            return None, (self._error(CrossValidationParseErrorKind.INVALID_CONFLICTING_CLAIMS, **common),)
        if relation is EvidenceRelation.SUPPORTS and (not matched_claims or conflicting_claims):
            return None, (self._error(CrossValidationParseErrorKind.DOMAIN_CONVERSION, **common),)
        if relation is EvidenceRelation.CONTRADICTS and not conflicting_claims:
            return None, (self._error(CrossValidationParseErrorKind.DOMAIN_CONVERSION, **common),)
        if relation is EvidenceRelation.UNRELATED and (matched_claims or conflicting_claims):
            return None, (self._error(CrossValidationParseErrorKind.DOMAIN_CONVERSION, **common),)
        return CrossValidationAssessmentEvidence(article_id=article_id, relation=relation, matched_claims=matched_claims, conflicting_claims=conflicting_claims), ()

    @staticmethod
    def _parse_index(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("index must be an integer")
        return value

    @staticmethod
    def _parse_score(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("confidence must be a number")
        if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
            raise ValueError("confidence must be finite integer")
        score: int = int(value)
        if not 0 <= score <= 100:
            raise ValueError("confidence must be between 0 and 100")
        return score

    @staticmethod
    def _parse_relation(value: object) -> EvidenceRelation:
        if not isinstance(value, str):
            raise ValueError("relation must be a string")
        if value == "supports":
            return EvidenceRelation.SUPPORTS
        if value == "conflicts":
            return EvidenceRelation.CONTRADICTS
        if value == "unrelated":
            return EvidenceRelation.UNRELATED
        raise ValueError("unsupported relation")

    @staticmethod
    def _normalize_strings(values: object, maximum: int, required: bool) -> Tuple[str, ...]:
        if not isinstance(values, list):
            raise ValueError("values must be a list")
        normalized: List[str] = []
        seen: Set[str] = set()
        for value in values:
            if not isinstance(value, str):
                raise ValueError("value must be a string")
            text: str = " ".join(value.split())
            if text and text not in seen:
                seen.add(text)
                normalized.append(text)
        if (required and not normalized) or len(normalized) > maximum:
            raise ValueError("values must be non-empty within maximum")
        return tuple(normalized)

    @staticmethod
    def _error(kind: CrossValidationParseErrorKind, event_index: int | None = None, evidence_index: int | None = None, candidate_id: str | None = None, article_id: str | None = None) -> CrossValidationParseError:
        return CrossValidationParseError(kind=kind, event_index=event_index, evidence_index=evidence_index, candidate_id=candidate_id, article_id=article_id)

    @staticmethod
    def _error_for_candidate(kind: CrossValidationParseErrorKind, event_index: int, candidates: Tuple[CrossValidationCandidate, ...]) -> CrossValidationParseError:
        return CrossValidationParseError(kind=kind, event_index=event_index, candidate_id=candidates[event_index].candidate_id)
