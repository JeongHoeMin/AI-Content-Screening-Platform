from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DeduplicationRelation(str, Enum):
    SAME = "same"
    DIFFERENT = "different"
    UNCERTAIN = "uncertain"


class EventDeduplicationPolicyConfig(BaseModel):
    """Immutable confidence boundary for policy-owned event merging."""

    model_config = ConfigDict(frozen=True)

    merge_confidence_at_least: int = Field(default=80, ge=0, le=100)


class EventDeduplicationPolicy:
    """Conservatively decides whether an LLM observation may merge events."""

    def __init__(self, config: EventDeduplicationPolicyConfig | None = None) -> None:
        self._config: EventDeduplicationPolicyConfig = config or EventDeduplicationPolicyConfig()

    def should_merge(self, relation: DeduplicationRelation, confidence: int) -> bool:
        return (
            relation is DeduplicationRelation.SAME
            and confidence >= self._config.merge_confidence_at_least
        )
