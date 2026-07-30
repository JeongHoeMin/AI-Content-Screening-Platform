from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.analyzers import DefaultImpactPolicy
from app.models import (
    CompanyRelation, CompanyResolutionStatus, CrossValidationStatus, EventFact,
    EventType, ExtractedCompany, ImpactDirection, ImpactExclusionReason,
    ImpactFilterResult, ImpactObservation, ImpactReasonCode, ImpactScope,
    ImpactUncertainty, ImpactAnalysis, NewsEvent, ResolvedCompany, ResolvedDecisionType,
    ResolvedNewsEvent, ResolvedTicker,
)


def build_event(
    decision: ResolvedDecisionType = ResolvedDecisionType.ACCEPT,
    status: CrossValidationStatus | None = None,
) -> ResolvedNewsEvent:
    company: ResolvedCompany = ResolvedCompany(name="Company", relation=CompanyRelation.DIRECT, ticker=ResolvedTicker(ticker="005930", exchange="KRX"), company_id="KRX-1", resolution_status=CompanyResolutionStatus.RESOLVED)
    event: NewsEvent = NewsEvent(title="Title", summary="Summary", event_type=EventType.CORPORATE_EVENT, event_facts=(EventFact.FACTORY_EXPANSION,), companies=[ExtractedCompany(name="Company", relation=CompanyRelation.DIRECT)], industries=["Industry"], keywords=["Keyword"], reasons=["Reason"])
    return ResolvedNewsEvent(event=event, companies=(company,), decision=decision, cross_validation_status=status)


def build_observation(event: ResolvedNewsEvent, direction: ImpactDirection = ImpactDirection.POSITIVE) -> ImpactObservation:
    return ImpactObservation(scope=ImpactScope.COMPANY, company=event.companies[0], event_fact=EventFact.FACTORY_EXPANSION, direction=direction, uncertainty=ImpactUncertainty.HIGH, reason_code=ImpactReasonCode.FACTORY_EXPANSION_POSITIVE)


def test_policy_uses_fixed_priority_for_multiple_exclusion_conditions() -> None:
    event: ResolvedNewsEvent = build_event(ResolvedDecisionType.REJECT)
    unresolved: ImpactObservation = build_observation(event).model_copy(update={
        "company": ResolvedCompany(name="Unresolved", relation=CompanyRelation.DIRECT, ticker=None),
        "direction": ImpactDirection.UNKNOWN,
    })

    result: ImpactFilterResult = DefaultImpactPolicy().filter(event, (unresolved,))[0]

    assert result == ImpactFilterResult(eligible=False, exclusion_reason=ImpactExclusionReason.EVENT_REJECTED)


def test_policy_filters_review_not_verified_and_unknown_direction() -> None:
    review_event: ResolvedNewsEvent = build_event(ResolvedDecisionType.REVIEW)
    assert DefaultImpactPolicy().filter(review_event, (build_observation(review_event),))[0].exclusion_reason is ImpactExclusionReason.EVENT_REVIEW_NOT_VERIFIED
    accepted_event: ResolvedNewsEvent = build_event()
    assert DefaultImpactPolicy().filter(accepted_event, (build_observation(accepted_event, ImpactDirection.UNKNOWN),))[0].exclusion_reason is ImpactExclusionReason.UNKNOWN_DIRECTION


def test_policy_excludes_unsupported_scope_after_event_gates() -> None:
    event: ResolvedNewsEvent = build_event()
    observation: ImpactObservation = ImpactObservation(
        scope=ImpactScope.INDUSTRY,
        event_fact=EventFact.FACTORY_EXPANSION,
        direction=ImpactDirection.POSITIVE,
        uncertainty=ImpactUncertainty.HIGH,
        reason_code=ImpactReasonCode.FACTORY_EXPANSION_POSITIVE,
    )

    result: ImpactFilterResult = DefaultImpactPolicy().filter(event, (observation,))[0]

    assert result.exclusion_reason is ImpactExclusionReason.UNSUPPORTED_SCOPE


@pytest.mark.parametrize(
    ("eligible", "reason"),
    [(True, ImpactExclusionReason.UNKNOWN_DIRECTION), (False, None)],
)
def test_filter_result_rejects_inconsistent_eligibility(eligible: bool, reason: ImpactExclusionReason | None) -> None:
    with pytest.raises(ValidationError):
        ImpactFilterResult(eligible=eligible, exclusion_reason=reason)


def test_analysis_rejects_observation_filter_length_mismatch() -> None:
    event: ResolvedNewsEvent = build_event()

    with pytest.raises(ValidationError, match="equal length"):
        ImpactAnalysis(event=event, observations=(build_observation(event),), filters=())
