from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from app.models.cross_validation import CrossValidationAssessmentResponse, CrossValidationCandidate

_SYSTEM: str = """Compare each candidate event with its related articles. Return only article IDs that support, partially match, or contradict the event; omitted related article IDs are unrelated. Assess matching and conflicting claims and confidence from 0 to 100. Provide one to three concise reasons. Do not decide a validation status and do not reveal chain-of-thought. Return only valid JSON matching this schema:\n{schema}\nDo not add properties, markdown fences, or explanatory text."""


def build_cross_validation_system_prompt() -> str:
    schema: Dict[str, Any] = CrossValidationAssessmentResponse.model_json_schema()
    return _SYSTEM.format(schema=json.dumps(schema, ensure_ascii=False))


def build_cross_validation_user_prompt(candidates: Tuple[CrossValidationCandidate, ...]) -> str:
    return "Cross validate these candidates:\n" + json.dumps([candidate.model_dump(mode="json") for candidate in candidates], ensure_ascii=False)
