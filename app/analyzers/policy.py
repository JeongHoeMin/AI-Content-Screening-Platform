from __future__ import annotations

from typing import Protocol, Tuple

from app.models.company_resolution import CompanyResolutionStatus
from app.models.cross_validation import CrossValidationStatus
from app.models.impact_analysis import (
    ImpactDirection,
    ImpactExclusionReason,
    ImpactFilterResult,
    ImpactObservation,
    ImpactScope,
)
from app.models.resolved_news_event import ResolvedDecisionType, ResolvedNewsEvent


class ImpactPolicy(Protocol):
    """Determines downstream eligibility without changing observations."""

    def filter(
        self,
        event: ResolvedNewsEvent,
        observations: Tuple[ImpactObservation, ...],
    ) -> Tuple[ImpactFilterResult, ...]:
        """Return one eligibility result in the same order as observations."""
        ...


class DefaultImpactPolicy:
    """Deterministic v1 filtering with a fixed exclusion precedence."""

    def filter(
        self,
        event: ResolvedNewsEvent,
        observations: Tuple[ImpactObservation, ...],
    ) -> Tuple[ImpactFilterResult, ...]:
        return tuple(self._filter_one(event, observation) for observation in observations)

    @staticmethod
    def _filter_one(
        event: ResolvedNewsEvent,
        observation: ImpactObservation,
    ) -> ImpactFilterResult:
        reason: ImpactExclusionReason | None = None
        if event.decision is ResolvedDecisionType.REJECT:
            reason = ImpactExclusionReason.EVENT_REJECTED
        elif (
            event.decision is ResolvedDecisionType.REVIEW
            and event.cross_validation_status
            not in (
                CrossValidationStatus.VERIFIED,
                CrossValidationStatus.PARTIALLY_VERIFIED,
            )
        ):
            reason = ImpactExclusionReason.EVENT_REVIEW_NOT_VERIFIED
        elif (
            observation.scope is ImpactScope.COMPANY
            and (
                observation.company is None
                or observation.company.resolution_status
                is not CompanyResolutionStatus.RESOLVED
            )
        ):
            reason = ImpactExclusionReason.COMPANY_NOT_RESOLVED
        elif (
            observation.scope is ImpactScope.COMPANY
            and observation.company is not None
            and observation.company.company_id is None
        ):
            reason = ImpactExclusionReason.COMPANY_IDENTITY_MISSING
        elif observation.scope is not ImpactScope.COMPANY:
            reason = ImpactExclusionReason.UNSUPPORTED_SCOPE
        elif observation.direction is ImpactDirection.UNKNOWN:
            reason = ImpactExclusionReason.UNKNOWN_DIRECTION

        if reason is None:
            return ImpactFilterResult(eligible=True)
        return ImpactFilterResult(eligible=False, exclusion_reason=reason)
