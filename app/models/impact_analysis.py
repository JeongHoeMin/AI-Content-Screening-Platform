from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.news_event import EventFact
from app.models.resolved_news_event import ResolvedCompany, ResolvedNewsEvent


class ImpactDirection(str, Enum):
    """Direction of an event fact's interpreted impact on a company."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class ImpactScope(str, Enum):
    """Audience scope to which an observation applies."""

    COMPANY = "company"
    INDUSTRY = "industry"
    MARKET = "market"
    MACRO = "macro"


class ImpactUncertainty(str, Enum):
    """Bounded confidence category assigned by the deterministic strategy."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImpactReasonCode(str, Enum):
    """Strategy-owned reason for a fact's impact direction."""

    FACTORY_EXPANSION_POSITIVE = "factory_expansion_positive"
    MASS_LAYOFF_NEGATIVE = "mass_layoff_negative"
    BANKRUPTCY_NEGATIVE = "bankruptcy_negative"
    PRODUCT_RELEASE_DIRECTION_UNKNOWN = "product_release_direction_unknown"
    CEO_INTERVIEW_DIRECTION_UNKNOWN = "ceo_interview_direction_unknown"


class ImpactExclusionReason(str, Enum):
    """Policy-owned reason an observation is not downstream evidence."""

    EVENT_REJECTED = "event_rejected"
    EVENT_REVIEW_NOT_VERIFIED = "event_review_not_verified"
    COMPANY_NOT_RESOLVED = "company_not_resolved"
    COMPANY_IDENTITY_MISSING = "company_identity_missing"
    UNSUPPORTED_SCOPE = "unsupported_scope"
    UNKNOWN_DIRECTION = "unknown_direction"


class ImpactObservation(BaseModel):
    """Immutable, audit-preserving impact interpretation for one event fact."""

    model_config = ConfigDict(frozen=True, revalidate_instances="never")

    scope: ImpactScope
    company: Optional[ResolvedCompany] = None
    event_fact: EventFact
    direction: ImpactDirection
    uncertainty: ImpactUncertainty
    reason_code: ImpactReasonCode

    @model_validator(mode="after")
    def _validate_scope_company(self) -> "ImpactObservation":
        if self.scope is ImpactScope.COMPANY and self.company is None:
            raise ValueError("COMPANY observations require a company")
        if self.scope is not ImpactScope.COMPANY and self.company is not None:
            raise ValueError("Non-COMPANY observations must not include a company")
        return self


class ImpactFilterResult(BaseModel):
    """Eligibility decision aligned one-to-one with an impact observation."""

    model_config = ConfigDict(frozen=True)

    eligible: bool
    exclusion_reason: Optional[ImpactExclusionReason] = None

    @model_validator(mode="after")
    def _validate_eligibility(self) -> "ImpactFilterResult":
        if self.eligible and self.exclusion_reason is not None:
            raise ValueError("Eligible result must not have an exclusion reason")
        if not self.eligible and self.exclusion_reason is None:
            raise ValueError("Ineligible result requires an exclusion reason")
        return self


@dataclass(frozen=True)
class CompanyImpact:
    """Legacy scoring evidence derived from one eligible observation."""

    company: ResolvedCompany
    direction: ImpactDirection


class ImpactAnalysis(BaseModel):
    """Immutable analysis snapshot preserving observations before filtering."""

    model_config = ConfigDict(frozen=True, revalidate_instances="never")

    event: ResolvedNewsEvent
    observations: Tuple[ImpactObservation, ...] = ()
    filters: Tuple[ImpactFilterResult, ...] = ()

    @model_validator(mode="after")
    def _validate_filter_alignment(self) -> "ImpactAnalysis":
        if len(self.observations) != len(self.filters):
            raise ValueError(
                "ImpactAnalysis observations and filters must have equal length"
            )
        return self
