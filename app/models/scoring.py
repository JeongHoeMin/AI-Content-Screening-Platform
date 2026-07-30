from __future__ import annotations

from math import fsum, isfinite
from enum import Enum
from typing import Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.impact_analysis import CompanyImpact, ImpactDirection
from app.models.resolved_news_event import ResolvedCompany


class ScoreFactor(str, Enum):
    """Stable category explaining how an evidence direction contributes."""

    POSITIVE_EVIDENCE = "positive_evidence"
    NEGATIVE_EVIDENCE = "negative_evidence"
    NON_DIRECTIONAL_EVIDENCE = "non_directional_evidence"


class ScoreReasonCode(str, Enum):
    """Safe scoring-policy reason for one direction weight."""

    POSITIVE_DIRECTION_WEIGHT = "positive_direction_weight"
    NEGATIVE_DIRECTION_WEIGHT = "negative_direction_weight"
    NEUTRAL_DIRECTION_WEIGHT = "neutral_direction_weight"
    UNKNOWN_DIRECTION_WEIGHT = "unknown_direction_weight"


class DirectionScoreEntry(BaseModel):
    """One finite direction-to-score mapping owned by the scoring policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    direction: ImpactDirection
    factor: ScoreFactor
    weight: float
    reason_code: ScoreReasonCode

    @field_validator("weight")
    @classmethod
    def _require_finite_weight(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Score weight must be finite")
        return value


class DirectionScoreCatalog(BaseModel):
    """Exhaustive immutable direction registry for one scoring policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: Tuple[DirectionScoreEntry, ...]

    @model_validator(mode="after")
    def _validate_complete_unique_coverage(self) -> "DirectionScoreCatalog":
        directions: Tuple[ImpactDirection, ...] = tuple(
            entry.direction for entry in self.entries
        )
        duplicate_directions: Tuple[ImpactDirection, ...] = tuple(
            direction for direction in ImpactDirection if directions.count(direction) > 1
        )
        missing_directions: Tuple[ImpactDirection, ...] = tuple(
            direction for direction in ImpactDirection if direction not in directions
        )
        if duplicate_directions or missing_directions:
            details: list[str] = []
            if duplicate_directions:
                details.append(
                    "Duplicate directions: "
                    + ", ".join(direction.name for direction in duplicate_directions)
                )
            if missing_directions:
                details.append(
                    "Missing directions: "
                    + ", ".join(direction.name for direction in missing_directions)
                )
            raise ValueError(
                "Direction Score Catalog must assign every impact direction exactly once. "
                + "; ".join(details)
            )
        return self

    def entry_for(self, direction: ImpactDirection) -> DirectionScoreEntry:
        """Return the guaranteed mapping for one valid impact direction."""
        for entry in self.entries:
            if entry.direction is direction:
                return entry
        raise RuntimeError(f"Missing score entry for direction: {direction.name}")


class ScoringPolicyConfig(BaseModel):
    """Single immutable policy input for an explainable scoring execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_version: str = Field(min_length=1)
    min_weight: float
    max_weight: float
    catalog: DirectionScoreCatalog

    @field_validator("policy_version")
    @classmethod
    def _require_non_blank_policy_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("policy_version must not be blank")
        return value

    @field_validator("min_weight", "max_weight")
    @classmethod
    def _require_finite_bound(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Scoring policy weight bounds must be finite")
        return value

    @model_validator(mode="after")
    def _validate_catalog_weights(self) -> "ScoringPolicyConfig":
        if self.min_weight > self.max_weight:
            raise ValueError("min_weight must not exceed max_weight")
        out_of_range: Tuple[ImpactDirection, ...] = tuple(
            entry.direction
            for entry in self.catalog.entries
            if entry.weight < self.min_weight or entry.weight > self.max_weight
        )
        if out_of_range:
            raise ValueError(
                "Catalog weights must be within configured bounds. Directions: "
                + ", ".join(direction.name for direction in out_of_range)
            )
        return self


class ScoreContribution(BaseModel):
    """Atomic score interpretation of one original CompanyImpact evidence item."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        revalidate_instances="never",
    )

    impact: CompanyImpact
    factor: ScoreFactor
    weight: float
    value: float
    reason_code: ScoreReasonCode

    @field_validator("weight", "value")
    @classmethod
    def _require_finite_value(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Score contribution values must be finite")
        return value

    @model_validator(mode="after")
    def _require_value_equals_weight(self) -> "ScoreContribution":
        if self.value != self.weight:
            raise ValueError("Score contribution value must equal weight in v1")
        return self


class CompanyScore(BaseModel):
    """Immutable score with atomic evidence-to-contribution provenance."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        revalidate_instances="never",
    )

    company: ResolvedCompany
    score: float
    contributions: Tuple[ScoreContribution, ...] = ()

    @field_validator("score")
    @classmethod
    def _require_finite_score(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Company score must be finite")
        return value

    @model_validator(mode="after")
    def _require_score_sum(self) -> "CompanyScore":
        if self.score != fsum(item.value for item in self.contributions):
            raise ValueError("Company score must equal the sum of contribution values")
        return self

    @property
    def evidences(self) -> Tuple[CompanyImpact, ...]:
        """Return original evidence identities in contribution order."""
        return tuple(item.impact for item in self.contributions)


class ScoringResult(BaseModel):
    """Final immutable result created by a ScoringStrategy execution."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        revalidate_instances="never",
    )

    policy_version: str = Field(min_length=1)
    companies: Tuple[CompanyScore, ...]

    @field_validator("policy_version")
    @classmethod
    def _require_non_blank_policy_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("policy_version must not be blank")
        return value


DEFAULT_DIRECTION_SCORE_CATALOG = DirectionScoreCatalog(
    entries=(
        DirectionScoreEntry(
            direction=ImpactDirection.POSITIVE,
            factor=ScoreFactor.POSITIVE_EVIDENCE,
            weight=1.0,
            reason_code=ScoreReasonCode.POSITIVE_DIRECTION_WEIGHT,
        ),
        DirectionScoreEntry(
            direction=ImpactDirection.NEGATIVE,
            factor=ScoreFactor.NEGATIVE_EVIDENCE,
            weight=-1.0,
            reason_code=ScoreReasonCode.NEGATIVE_DIRECTION_WEIGHT,
        ),
        DirectionScoreEntry(
            direction=ImpactDirection.NEUTRAL,
            factor=ScoreFactor.NON_DIRECTIONAL_EVIDENCE,
            weight=0.0,
            reason_code=ScoreReasonCode.NEUTRAL_DIRECTION_WEIGHT,
        ),
        DirectionScoreEntry(
            direction=ImpactDirection.UNKNOWN,
            factor=ScoreFactor.NON_DIRECTIONAL_EVIDENCE,
            weight=0.0,
            reason_code=ScoreReasonCode.UNKNOWN_DIRECTION_WEIGHT,
        ),
    )
)

DEFAULT_SCORING_POLICY_CONFIG = ScoringPolicyConfig(
    policy_version="v1",
    min_weight=-1.0,
    max_weight=1.0,
    catalog=DEFAULT_DIRECTION_SCORE_CATALOG,
)
