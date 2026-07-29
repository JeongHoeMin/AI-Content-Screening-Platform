from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from app.models.screening import ScreeningAssessmentResponse, ScreeningCandidate

_SYSTEM_PROMPT: str = """You assess extracted news events for an AI screening pipeline.
Return exactly one assessment for every input candidate using its unchanged candidate_id.
Assess relevance, importance, and credibility as integers from 0 to 100.
Set requires_cross_validation when the event needs independent verification, such as
when its source evidence is weak, unofficial, unusually consequential, or disputed.
Return between 1 and 3 concise user-readable reasons for each candidate,
grounded in the provided article and event.
Do not make ACCEPT, REVIEW, or REJECT decisions; a deterministic policy owns them.
Do not reveal private chain-of-thought or internal reasoning.
Return only valid JSON matching this schema:
{response_schema}
Do not add properties, markdown fences, or explanatory text.
"""
_USER_PROMPT: str = "Assess these extracted event candidates:\n{candidates_json}"


def build_screening_system_prompt() -> str:
    """Render screening instructions with the shared assessment response schema."""
    response_schema: Dict[str, Any] = (
        ScreeningAssessmentResponse.model_json_schema()
    )
    schema_json: str = json.dumps(response_schema, ensure_ascii=False)
    return _SYSTEM_PROMPT.format(response_schema=schema_json)


def build_screening_user_prompt(
    candidates: Tuple[ScreeningCandidate, ...],
) -> str:
    """Render article-contextual event candidates for one screening batch."""
    candidate_data: list[Dict[str, Any]] = [
        candidate.model_dump(mode="json") for candidate in candidates
    ]
    candidates_json: str = json.dumps(candidate_data, ensure_ascii=False)
    return _USER_PROMPT.format(candidates_json=candidates_json)
