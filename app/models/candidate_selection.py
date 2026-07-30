from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.recommendation import RecommendationAction, RecommendationDecision


class CandidateStatus(str, Enum):
    """Selection outcome for one recommendation decision."""

    SELECTED = "selected"
    NOT_ELIGIBLE = "not_eligible"
    OUTSIDE_LIMIT = "outside_limit"


class CandidateReasonCode(str, Enum):
    """Stable policy reason for a candidate-selection outcome."""

    SELECTED_STRONG_BUY = "selected_strong_buy"
    SELECTED_BUY = "selected_buy"
    EXCLUDED_HOLD = "excluded_hold"
    EXCLUDED_SELL = "excluded_sell"
    EXCLUDED_STRONG_SELL = "excluded_strong_sell"
    EXCLUDED_OUTSIDE_CANDIDATE_LIMIT = "excluded_outside_candidate_limit"


class RecommendationRankEntry(BaseModel):
    """One action's eligibility and deterministic catalog priority."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: RecommendationAction
    eligible: bool
    priority: int = Field(ge=0)


class RecommendationRankCatalog(BaseModel):
    """Exhaustive immutable ranking registry for one candidate policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: Tuple[RecommendationRankEntry, ...]

    @model_validator(mode="after")
    def _require_complete_unique_entries(self) -> "RecommendationRankCatalog":
        actions: Tuple[RecommendationAction, ...] = tuple(
            entry.action for entry in self.entries
        )
        duplicate_actions: Tuple[RecommendationAction, ...] = tuple(
            action for action in RecommendationAction if actions.count(action) > 1
        )
        missing_actions: Tuple[RecommendationAction, ...] = tuple(
            action for action in RecommendationAction if action not in actions
        )
        priorities: Tuple[int, ...] = tuple(entry.priority for entry in self.entries)
        duplicate_priorities: Tuple[int, ...] = tuple(
            priority for priority in priorities if priorities.count(priority) > 1
        )
        if duplicate_actions or missing_actions or duplicate_priorities:
            details: list[str] = []
            if duplicate_actions:
                details.append(
                    "Duplicate actions: "
                    + ", ".join(action.name for action in duplicate_actions)
                )
            if missing_actions:
                details.append(
                    "Missing actions: "
                    + ", ".join(action.name for action in missing_actions)
                )
            if duplicate_priorities:
                details.append(
                    "Duplicate priorities: "
                    + ", ".join(str(priority) for priority in sorted(set(duplicate_priorities)))
                )
            raise ValueError(
                "Recommendation Rank Catalog must assign every action exactly once. "
                + "; ".join(details)
            )
        return self

    def entry_for(self, action: RecommendationAction) -> RecommendationRankEntry:
        """Return the guaranteed ranking entry for one recommendation action."""
        for entry in self.entries:
            if entry.action is action:
                return entry
        raise RuntimeError(f"Missing ranking entry for action: {action.name}")


class RankingPolicyConfig(BaseModel):
    """Single immutable policy input for a candidate-selection execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(min_length=1)
    max_candidates: int = Field(ge=1)
    catalog: RecommendationRankCatalog

    @field_validator("policy_version")
    @classmethod
    def _require_non_blank_policy_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("policy_version must not be blank")
        return value


class CandidateEvaluation(BaseModel):
    """Atomic immutable candidate-policy evaluation of one decision."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="never")

    decision: RecommendationDecision
    status: CandidateStatus
    reason_code: CandidateReasonCode
    input_index: int = Field(ge=0)
    rank: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _require_consistent_evaluation(self) -> "CandidateEvaluation":
        action: RecommendationAction = self.decision.action
        if self.status is CandidateStatus.SELECTED:
            expected_reason: CandidateReasonCode | None = _SELECTED_REASONS.get(action)
            if self.rank is None or self.reason_code is not expected_reason:
                raise ValueError("Selected candidate must have matching action reason and rank")
        elif self.status is CandidateStatus.NOT_ELIGIBLE:
            expected_reason = _NOT_ELIGIBLE_REASONS.get(action)
            if self.rank is not None or self.reason_code is not expected_reason:
                raise ValueError("Not eligible candidate must have matching action reason and no rank")
        else:
            if (
                action not in _SELECTED_REASONS
                or self.rank is not None
                or self.reason_code is not CandidateReasonCode.EXCLUDED_OUTSIDE_CANDIDATE_LIMIT
            ):
                raise ValueError("Outside-limit candidate must be eligible with no rank")
        return self


class CandidateSelectionResult(BaseModel):
    """Final immutable audit trail created by a candidate-selection policy."""

    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="never")

    policy_version: str = Field(min_length=1)
    evaluations: Tuple[CandidateEvaluation, ...]

    @field_validator("policy_version")
    @classmethod
    def _require_non_blank_policy_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("policy_version must not be blank")
        return value

    @model_validator(mode="after")
    def _require_canonical_audit_order(self) -> "CandidateSelectionResult":
        expected_indexes: Tuple[int, ...] = tuple(range(len(self.evaluations)))
        actual_indexes: Tuple[int, ...] = tuple(
            evaluation.input_index for evaluation in self.evaluations
        )
        if actual_indexes != expected_indexes:
            raise ValueError("Candidate evaluations must be stored in input_index order")
        ranks: Tuple[int, ...] = tuple(
            evaluation.rank
            for evaluation in self.evaluations
            if evaluation.status is CandidateStatus.SELECTED
        )
        if tuple(sorted(ranks)) != tuple(range(1, len(ranks) + 1)):
            raise ValueError("Selected candidate ranks must be contiguous starting at one")
        return self

    @property
    def candidates(self) -> Tuple[CandidateEvaluation, ...]:
        """Return selected evaluations in ascending candidate rank."""
        return tuple(
            sorted(
                (item for item in self.evaluations if item.status is CandidateStatus.SELECTED),
                key=lambda item: item.rank if item.rank is not None else 0,
            )
        )

    @property
    def excluded(self) -> Tuple[CandidateEvaluation, ...]:
        """Return non-selected evaluations in original input order."""
        return tuple(
            item for item in self.evaluations if item.status is not CandidateStatus.SELECTED
        )

    @property
    def decisions(self) -> Tuple[RecommendationDecision, ...]:
        """Return original decision identities in canonical input order."""
        return tuple(item.decision for item in self.evaluations)


_SELECTED_REASONS: dict[RecommendationAction, CandidateReasonCode] = {
    RecommendationAction.STRONG_BUY: CandidateReasonCode.SELECTED_STRONG_BUY,
    RecommendationAction.BUY: CandidateReasonCode.SELECTED_BUY,
}

_NOT_ELIGIBLE_REASONS: dict[RecommendationAction, CandidateReasonCode] = {
    RecommendationAction.HOLD: CandidateReasonCode.EXCLUDED_HOLD,
    RecommendationAction.SELL: CandidateReasonCode.EXCLUDED_SELL,
    RecommendationAction.STRONG_SELL: CandidateReasonCode.EXCLUDED_STRONG_SELL,
}

DEFAULT_RECOMMENDATION_RANK_CATALOG = RecommendationRankCatalog(
    entries=(
        RecommendationRankEntry(action=RecommendationAction.STRONG_BUY, eligible=True, priority=0),
        RecommendationRankEntry(action=RecommendationAction.BUY, eligible=True, priority=1),
        RecommendationRankEntry(action=RecommendationAction.HOLD, eligible=False, priority=2),
        RecommendationRankEntry(action=RecommendationAction.SELL, eligible=False, priority=3),
        RecommendationRankEntry(action=RecommendationAction.STRONG_SELL, eligible=False, priority=4),
    )
)

DEFAULT_RANKING_POLICY_CONFIG = RankingPolicyConfig(
    policy_version="v1",
    max_candidates=10,
    catalog=DEFAULT_RECOMMENDATION_RANK_CATALOG,
)
