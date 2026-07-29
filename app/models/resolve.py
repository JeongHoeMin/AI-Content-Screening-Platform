from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.resolved_news_event import ResolvedDecisionType


class ResolveDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: ResolvedDecisionType
    reasons: tuple[str, ...] = Field(min_length=1)

    @field_validator("reasons")
    @classmethod
    def _validate_reasons(cls, reasons: tuple[str, ...]) -> tuple[str, ...]:
        if any(not reason.strip() for reason in reasons):
            raise ValueError("Resolve decision reasons must not be blank")
        return reasons
