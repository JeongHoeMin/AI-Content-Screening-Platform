from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    CompanyRelation,
    ExtractedCompany,
    NewsEvent,
    ScreeningAssessment,
    ScreeningDecisionType,
)
from app.screeners import DefaultScreeningPolicy, ScreeningPolicyConfig


def build_event() -> NewsEvent:
    return NewsEvent(
        title="Investment announcement",
        summary="A company announced a material investment.",
        companies=[
            ExtractedCompany(
                name="Samsung Electronics",
                relation=CompanyRelation.DIRECT,
            )
        ],
        industries=["Semiconductors"],
        keywords=["Investment"],
        reasons=["Explicit source fact"],
    )


def build_assessment(
    relevance: int = 80,
    importance: int = 80,
    credibility: int = 80,
    requires_cross_validation: bool = False,
) -> ScreeningAssessment:
    return ScreeningAssessment(
        candidate_id="article-1:0",
        relevance=relevance,
        importance=importance,
        credibility=credibility,
        requires_cross_validation=requires_cross_validation,
        reasons=("The event has a material stated impact.",),
    )


@pytest.mark.parametrize("field", ["relevance", "importance", "credibility"])
def test_assessment_rejects_scores_outside_zero_to_one_hundred(field: str) -> None:
    values: dict[str, object] = build_assessment().model_dump()
    values[field] = 101

    with pytest.raises(ValidationError):
        ScreeningAssessment.model_validate(values)


def test_assessment_requires_a_non_blank_reason() -> None:
    values: dict[str, object] = build_assessment().model_dump()
    values["reasons"] = ("   ",)

    with pytest.raises(ValidationError):
        ScreeningAssessment.model_validate(values)


def test_policy_applies_reject_before_cross_validation_review() -> None:
    event: NewsEvent = build_event()
    decision = DefaultScreeningPolicy().decide(
        event,
        build_assessment(relevance=39, requires_cross_validation=True),
    )

    assert decision.decision is ScreeningDecisionType.REJECT
    assert decision.event is event


def test_policy_applies_cross_validation_review_before_accept() -> None:
    decision = DefaultScreeningPolicy().decide(
        build_event(),
        build_assessment(requires_cross_validation=True),
    )

    assert decision.decision is ScreeningDecisionType.REVIEW


def test_policy_accepts_only_when_all_accept_thresholds_are_met() -> None:
    policy: DefaultScreeningPolicy = DefaultScreeningPolicy()

    assert policy.decide(build_event(), build_assessment()).decision is ScreeningDecisionType.ACCEPT
    assert (
        policy.decide(build_event(), build_assessment(credibility=69)).decision
        is ScreeningDecisionType.REVIEW
    )


def test_policy_uses_custom_threshold_configuration() -> None:
    policy: DefaultScreeningPolicy = DefaultScreeningPolicy(
        ScreeningPolicyConfig(
            reject_relevance_threshold=20,
            reject_importance_threshold=20,
            accept_relevance_threshold=60,
            accept_importance_threshold=60,
            accept_credibility_threshold=60,
        )
    )

    decision = policy.decide(
        build_event(),
        build_assessment(relevance=60, importance=60, credibility=60),
    )

    assert decision.decision is ScreeningDecisionType.ACCEPT


def test_policy_config_rejects_inconsistent_thresholds() -> None:
    with pytest.raises(ValidationError):
        ScreeningPolicyConfig(
            reject_relevance_threshold=71,
            accept_relevance_threshold=70,
        )
