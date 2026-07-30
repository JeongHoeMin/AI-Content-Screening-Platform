from __future__ import annotations

from typing import Protocol, Tuple

from app.models.company_resolution import CompanyResolutionStatus
from app.models.cross_validation import CrossValidationStatus
from app.models.impact_analysis import (
    ImpactDirection,
    ImpactExclusionReason,
    ImpactEvaluation,
    ImpactObservation,
    ImpactScope,
)
from app.models.resolved_news_event import ResolvedDecisionType, ResolvedNewsEvent


class ImpactPolicy(Protocol):
    """Creates immutable evaluations without changing strategy observations."""

    def evaluate(
        self,
        event: ResolvedNewsEvent,
        observations: Tuple[ImpactObservation, ...],
    ) -> Tuple[ImpactEvaluation, ...]:
        """Return one paired evaluation in the same order as observations."""
        ...


class DefaultImpactPolicy:
    """Deterministic v1 filtering with a fixed exclusion precedence."""

    def evaluate(
        self,
        event: ResolvedNewsEvent,
        observations: Tuple[ImpactObservation, ...],
    ) -> Tuple[ImpactEvaluation, ...]:
        return tuple(self._evaluate_one(event, observation) for observation in observations)

    @staticmethod
    def _evaluate_one(
        event: ResolvedNewsEvent,
        observation: ImpactObservation,
    ) -> ImpactEvaluation:
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
            return ImpactEvaluation(observation=observation, eligible=True)
        return ImpactEvaluation(
            observation=observation,
            eligible=False,
            exclusion_reason=reason,
        )
