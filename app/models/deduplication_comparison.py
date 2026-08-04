from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class DeduplicationComparisonResponseItem(BaseModel):
    """Untrusted structured LLM observation for one deterministic candidate pair."""

    model_config = ConfigDict(extra="forbid")

    candidate_index: object = None
    relation: object = None
    confidence: object = None
    reasons: List[object] = Field(default_factory=list)


class DeduplicationComparisonResponse(BaseModel):
    """Provider-validated envelope parsed again against requested candidates."""

    model_config = ConfigDict(extra="forbid")

    comparisons: List[DeduplicationComparisonResponseItem]
