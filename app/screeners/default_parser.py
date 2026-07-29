from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Set, Tuple

from pydantic import ValidationError

from app.models.screening import (
    ScreeningAssessment,
    ScreeningAssessmentResponse,
    ScreeningAssessmentResponseItem,
    ScreeningCandidate,
    ScreeningParseError,
    ScreeningParseErrorKind,
    ScreeningParseResult,
)
from app.screeners.parser import ScreeningAssessmentParser


class DefaultScreeningAssessmentParser(ScreeningAssessmentParser):
    """Restores valid assessments by event index without discarding siblings."""

    def parse(
        self,
        response: ScreeningAssessmentResponse,
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> ScreeningParseResult:
        valid_indexes: Set[int] = set(range(len(candidates)))
        indexed_items: List[tuple[int, ScreeningAssessmentResponseItem]] = []
        errors: List[ScreeningParseError] = []
        for item in response.assessments:
            try:
                event_index: int = self._parse_event_index(item.event_index)
            except ValueError:
                errors.append(
                    ScreeningParseError(
                        kind=ScreeningParseErrorKind.INVALID_EVENT_INDEX,
                    )
                )
                continue
            indexed_items.append((event_index, item))
        counts: Counter[int] = Counter(
            event_index for event_index, _ in indexed_items
        )
        duplicate_indexes: Set[int] = {
            event_index for event_index, count in counts.items() if count > 1
        }
        response_by_index: Dict[int, ScreeningAssessmentResponseItem] = {}
        invalid_indexes: Set[int] = set()

        for event_index, item in indexed_items:
            if event_index not in valid_indexes:
                errors.append(
                    ScreeningParseError(
                        kind=ScreeningParseErrorKind.INVALID_EVENT_INDEX,
                        event_index=event_index,
                    )
                )
                continue
            if event_index in duplicate_indexes:
                invalid_indexes.add(event_index)
                continue
            response_by_index[event_index] = item

        for event_index in sorted(duplicate_indexes & valid_indexes):
            errors.append(
                self._error(
                    ScreeningParseErrorKind.DUPLICATE_EVENT_INDEX,
                    event_index,
                    candidates,
                )
            )

        assessments_by_index: Dict[int, ScreeningAssessment] = {}
        for event_index, item in response_by_index.items():
            assessment, error = self._map_assessment(item, event_index, candidates)
            if assessment is not None:
                assessments_by_index[event_index] = assessment
            elif error is not None:
                errors.append(error)
                invalid_indexes.add(event_index)

        for event_index in range(len(candidates)):
            if event_index not in assessments_by_index and event_index not in invalid_indexes:
                errors.append(
                    self._error(
                        ScreeningParseErrorKind.MISSING_EVENT_INDEX,
                        event_index,
                        candidates,
                    )
                )

        return ScreeningParseResult(
            assessments=tuple(
                assessments_by_index[event_index]
                for event_index in range(len(candidates))
                if event_index in assessments_by_index
            ),
            errors=tuple(errors),
        )

    def _map_assessment(
        self,
        item: ScreeningAssessmentResponseItem,
        event_index: int,
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> tuple[ScreeningAssessment | None, ScreeningParseError | None]:
        try:
            relevance: int = self._parse_integer_score(item.relevance)
            importance: int = self._parse_integer_score(item.importance)
            credibility: int = self._parse_integer_score(item.credibility)
        except ValueError:
            return None, self._error(
                ScreeningParseErrorKind.INVALID_SCORE,
                event_index,
                candidates,
            )
        try:
            requires_cross_validation: bool = self._parse_cross_validation_flag(
                item.requires_cross_validation
            )
        except ValueError:
            return None, self._error(
                ScreeningParseErrorKind.INVALID_CROSS_VALIDATION_FLAG,
                event_index,
                candidates,
            )
        try:
            reasons: Tuple[str, ...] = self._normalize_reasons(item.reasons)
        except ValueError:
            return None, self._error(
                ScreeningParseErrorKind.INVALID_REASONS,
                event_index,
                candidates,
            )
        try:
            return (
                ScreeningAssessment(
                    candidate_id=candidates[event_index].candidate_id,
                    relevance=relevance,
                    importance=importance,
                    credibility=credibility,
                    requires_cross_validation=requires_cross_validation,
                    reasons=reasons,
                ),
                None,
            )
        except ValidationError:
            return None, self._error(
                ScreeningParseErrorKind.DOMAIN_CONVERSION,
                event_index,
                candidates,
            )

    @staticmethod
    def _parse_event_index(value: object) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("event index must be an integer")
        return value

    @staticmethod
    def _parse_integer_score(value: object) -> int:
        if isinstance(value, bool):
            raise ValueError("score must not be boolean")
        if not isinstance(value, (int, float)):
            raise ValueError("score must be a JSON number")
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("score must be finite")
            if not value.is_integer():
                raise ValueError("score must be an integer")
        score: int = int(value)
        if not 0 <= score <= 100:
            raise ValueError("score must be between 0 and 100")
        return score

    @staticmethod
    def _parse_cross_validation_flag(value: object) -> bool:
        if type(value) is not bool:
            raise ValueError("requires_cross_validation must be a boolean")
        return value

    @staticmethod
    def _normalize_reasons(values: object) -> Tuple[str, ...]:
        if not isinstance(values, list):
            raise ValueError("reasons must be a list")
        seen: Set[str] = set()
        normalized: List[str] = []
        for value in values:
            if not isinstance(value, str):
                raise ValueError("every reason must be a string")
            reason: str = " ".join(value.split())
            if reason and reason not in seen:
                seen.add(reason)
                normalized.append(reason)
        if not normalized:
            raise ValueError("reasons must not be empty")
        if len(normalized) > 3:
            raise ValueError("reasons must contain at most three entries")
        return tuple(normalized)

    @staticmethod
    def _error(
        kind: ScreeningParseErrorKind,
        event_index: int,
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> ScreeningParseError:
        return ScreeningParseError(
            kind=kind,
            event_index=event_index,
            candidate_id=candidates[event_index].candidate_id,
        )
