from __future__ import annotations

from enum import Enum
from math import isfinite
from typing import Any, Mapping, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.scoring import CompanyScore


class RecommendationAction(str, Enum):
    """Investment action selected by a recommendation policy."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class RecommendationReasonCode(str, Enum):
    """Stable policy reason for a recommendation action."""

    SCORE_AT_OR_ABOVE_STRONG_BUY_THRESHOLD = (
        "score_at_or_above_strong_buy_threshold"
    )
    SCORE_AT_OR_ABOVE_BUY_THRESHOLD = "score_at_or_above_buy_threshold"
    SCORE_WITHIN_HOLD_RANGE = "score_within_hold_range"
    SCORE_AT_OR_BELOW_SELL_THRESHOLD = "score_at_or_below_sell_threshold"
    SCORE_AT_OR_BELOW_STRONG_SELL_THRESHOLD = (
        "score_at_or_below_strong_sell_threshold"
    )


class RecommendationThresholdSnapshot(BaseModel):
    """Validated immutable threshold values for one recommendation policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strong_buy_threshold: float
    buy_threshold: float
    sell_threshold: float
    strong_sell_threshold: float

    @field_validator(
        "strong_buy_threshold",
        "buy_threshold",
        "sell_threshold",
        "strong_sell_threshold",
    )
    @classmethod
    def _require_finite_threshold(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Recommendation thresholds must be finite")
        return value

    @model_validator(mode="after")
    def _require_strict_threshold_order(self) -> "RecommendationThresholdSnapshot":
        if not (
            self.strong_sell_threshold
            < self.sell_threshold
            < self.buy_threshold
            < self.strong_buy_threshold
        ):
            raise ValueError(
                "Recommendation thresholds must satisfy "
                "strong_sell < sell < buy < strong_buy"
            )
        return self


class RecommendationPolicyConfig(BaseModel):
    """Single immutable policy input for a recommendation execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(min_length=1)
    threshold_snapshot: RecommendationThresholdSnapshot

    @field_validator("policy_version")
    @classmethod
    def _require_non_blank_policy_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("policy_version must not be blank")
        return value


class RecommendationDecision(BaseModel):
    """Atomic immutable policy evaluation of one CompanyScore."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        revalidate_instances="never",
    )

    company_score: CompanyScore
    action: RecommendationAction
    reason_code: RecommendationReasonCode
    threshold_snapshot: RecommendationThresholdSnapshot

    @property
    def score(self) -> float:
        """Expose the score without duplicating the CompanyScore value."""
        return self.company_score.score

    @property
    def recommendation(self) -> RecommendationAction:
        """Provide the former decision attribute as a read-only alias."""
        return self.action

    @model_validator(mode="after")
    def _require_consistent_policy_evaluation(self) -> "RecommendationDecision":
        expected_action, expected_reason = self._expected_evaluation(
            self.company_score.score,
            self.threshold_snapshot,
        )
        if self.action is not expected_action or self.reason_code is not expected_reason:
            raise ValueError(
                "Recommendation decision action and reason_code must match score "
                "and threshold_snapshot"
            )
        return self

    @staticmethod
    def _expected_evaluation(
        score: float,
        thresholds: RecommendationThresholdSnapshot,
    ) -> tuple[RecommendationAction, RecommendationReasonCode]:
        if score >= thresholds.strong_buy_threshold:
            return (
                RecommendationAction.STRONG_BUY,
                RecommendationReasonCode.SCORE_AT_OR_ABOVE_STRONG_BUY_THRESHOLD,
            )
        if score >= thresholds.buy_threshold:
            return (
                RecommendationAction.BUY,
                RecommendationReasonCode.SCORE_AT_OR_ABOVE_BUY_THRESHOLD,
            )
        if score > thresholds.sell_threshold:
            return (
                RecommendationAction.HOLD,
                RecommendationReasonCode.SCORE_WITHIN_HOLD_RANGE,
            )
        if score > thresholds.strong_sell_threshold:
            return (
                RecommendationAction.SELL,
                RecommendationReasonCode.SCORE_AT_OR_BELOW_SELL_THRESHOLD,
            )
        return (
            RecommendationAction.STRONG_SELL,
            RecommendationReasonCode.SCORE_AT_OR_BELOW_STRONG_SELL_THRESHOLD,
        )


class RecommendationResult(BaseModel):
    """Final immutable result created by a RecommendationPolicy execution."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        revalidate_instances="never",
    )

    policy_version: str = Field(min_length=1)
    decisions: Tuple[RecommendationDecision, ...]

    @field_validator("policy_version")
    @classmethod
    def _require_non_blank_policy_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("policy_version must not be blank")
        return value

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_companies_payload(cls, value: Any) -> Any:
        """Read the stable CLI representation without storing it internally."""
        if not isinstance(value, Mapping) or "decisions" in value or "companies" not in value:
            return value
        raw_companies: object = value["companies"]
        if not isinstance(raw_companies, (list, tuple)):
            return value
        decisions: list[dict[str, object]] = []
        for raw_company in raw_companies:
            if not isinstance(raw_company, Mapping):
                return value
            action: RecommendationAction = RecommendationAction(
                raw_company["recommendation"]
            )
            decisions.append(
                {
                    "company_score": raw_company["score"],
                    "action": action,
                    "reason_code": _REASON_CODES_BY_ACTION[action],
                    "threshold_snapshot": DEFAULT_RECOMMENDATION_THRESHOLD_SNAPSHOT,
                }
            )
        return {
            "policy_version": DEFAULT_RECOMMENDATION_POLICY_CONFIG.policy_version,
            "decisions": decisions,
        }

    @property
    def companies(self) -> Tuple[RecommendationDecision, ...]:
        """Expose decisions through the former result collection name."""
        return self.decisions


# Compatibility names retained for existing imports during the Domain migration.
Recommendation = RecommendationAction
CompanyRecommendation = RecommendationDecision


DEFAULT_RECOMMENDATION_THRESHOLD_SNAPSHOT = RecommendationThresholdSnapshot(
    strong_buy_threshold=2.0,
    buy_threshold=1.0,
    sell_threshold=-1.0,
    strong_sell_threshold=-2.0,
)

DEFAULT_RECOMMENDATION_POLICY_CONFIG = RecommendationPolicyConfig(
    policy_version="v1",
    threshold_snapshot=DEFAULT_RECOMMENDATION_THRESHOLD_SNAPSHOT,
)

_REASON_CODES_BY_ACTION: dict[RecommendationAction, RecommendationReasonCode] = {
    RecommendationAction.STRONG_BUY: RecommendationReasonCode.SCORE_AT_OR_ABOVE_STRONG_BUY_THRESHOLD,
    RecommendationAction.BUY: RecommendationReasonCode.SCORE_AT_OR_ABOVE_BUY_THRESHOLD,
    RecommendationAction.HOLD: RecommendationReasonCode.SCORE_WITHIN_HOLD_RANGE,
    RecommendationAction.SELL: RecommendationReasonCode.SCORE_AT_OR_BELOW_SELL_THRESHOLD,
    RecommendationAction.STRONG_SELL: RecommendationReasonCode.SCORE_AT_OR_BELOW_STRONG_SELL_THRESHOLD,
}
