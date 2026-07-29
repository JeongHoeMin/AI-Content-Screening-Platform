from __future__ import annotations

from typing import List

from pydantic import BaseModel


class EvaluationResponseItem(BaseModel):
    """Shape of one LLM-provided post evaluation."""

    post_id: str
    score: int
    is_candidate: bool
    reasons: List[str]


class EvaluationResponse(BaseModel):
    """Official response contract shared by the prompt, LLM, and parser."""

    posts: List[EvaluationResponseItem]
