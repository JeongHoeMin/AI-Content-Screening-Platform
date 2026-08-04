from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    CompanyRelation,
    CredibilityScorecard,
    EventType,
    ExtractedCompany,
    ImportanceScorecard,
    NewsEvent,
    RelevanceScorecard,
    ScreeningAssessment,
    ScreeningScorecard,
    ScreeningDecisionType,
)
from app.screeners import DefaultScreeningPolicy, ScreeningPolicyConfig
from app.screeners import ScreeningScorecardPolicy


def build_event() -> NewsEvent:
    return NewsEvent(
        title="Investment announcement",
        summary="A company announced a material investment.",
        event_type=EventType.CORPORATE_EVENT,
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
        scorecard=ScreeningScorecardPolicy().calculate(
            ScreeningScorecard(
                relevance=RelevanceScorecard(
                    theme_directness=relevance, topic_match=relevance,
                    market_transmission_path=relevance, reason="관련성 근거",
                ),
                importance=ImportanceScorecard(
                    impact_magnitude=importance, scope_and_spillover=importance,
                    time_sensitivity=importance, reason="중요도 근거",
                ),
                credibility=CredibilityScorecard(
                    source_authority=credibility, evidence_specificity=credibility,
                    corroboration_and_uncertainty=credibility, reason="신뢰도 근거",
                ),
            )
        ),
        requires_cross_validation=requires_cross_validation,
        reasons=("The event has a material stated impact.",),
    )


def test_assessment_rejects_scorecard_scores_outside_zero_to_one_hundred() -> None:
    values: dict[str, object] = build_assessment().model_dump()
    scorecard: dict[str, object] = values["scorecard"]  # type: ignore[assignment]
    relevance: dict[str, object] = scorecard["relevance"]  # type: ignore[index,assignment]
    relevance["theme_directness"] = 101

    with pytest.raises(ValidationError):
        ScreeningAssessment.model_validate(values)


def test_assessment_requires_a_non_blank_reason() -> None:
    values: dict[str, object] = build_assessment().model_dump()
    values["reasons"] = ("   ",)

    with pytest.raises(ValidationError):
        ScreeningAssessment.model_validate(values)


def test_assessment_limits_reasons_to_three() -> None:
    values: dict[str, object] = build_assessment().model_dump()
    values["reasons"] = ("One", "Two", "Three", "Four")

    with pytest.raises(ValidationError):
        ScreeningAssessment.model_validate(values)


def test_policy_rejects_before_cross_validation_review() -> None:
    event: NewsEvent = build_event()
    decision = DefaultScreeningPolicy().decide(
        event,
        build_assessment(relevance=39, requires_cross_validation=True),
    )

    assert decision.decision is ScreeningDecisionType.REJECT
    assert decision.event is event


def test_policy_cross_validation_downgrades_accept_to_review() -> None:
    decision = DefaultScreeningPolicy().decide(
        build_event(),
        build_assessment(requires_cross_validation=True),
    )

    assert decision.decision is ScreeningDecisionType.REVIEW


def test_policy_enforces_reject_boundaries_and_defaults_to_review_at_forty() -> None:
    policy: DefaultScreeningPolicy = DefaultScreeningPolicy()

    assert (
        policy.decide(build_event(), build_assessment(relevance=39)).decision
        is ScreeningDecisionType.REJECT
    )
    assert (
        policy.decide(build_event(), build_assessment(importance=39)).decision
        is ScreeningDecisionType.REJECT
    )
    assert (
        policy.decide(
            build_event(),
            build_assessment(relevance=40, importance=40, credibility=100),
        ).decision
        is ScreeningDecisionType.REVIEW
    )


@pytest.mark.parametrize("field", ["relevance", "importance", "credibility"])
def test_policy_requires_every_accept_boundary_at_least_seventy(field: str) -> None:
    policy: DefaultScreeningPolicy = DefaultScreeningPolicy()
    values: dict[str, int] = {
        "relevance": 70,
        "importance": 70,
        "credibility": 70,
    }

    assert (
        policy.decide(build_event(), build_assessment(**values)).decision
        is ScreeningDecisionType.ACCEPT
    )
    values[field] = 69
    assert policy.decide(build_event(), build_assessment(**values)).decision is ScreeningDecisionType.REVIEW


def test_default_policy_uses_default_config_when_none_is_supplied() -> None:
    policy: DefaultScreeningPolicy = DefaultScreeningPolicy(config=None)

    assert (
        policy.decide(build_event(), build_assessment(relevance=39)).decision
        is ScreeningDecisionType.REJECT
    )


def test_default_policy_uses_supplied_config() -> None:
    policy: DefaultScreeningPolicy = DefaultScreeningPolicy(
        ScreeningPolicyConfig(
            reject_relevance_below=50,
            reject_importance_below=50,
            accept_relevance_at_least=80,
            accept_importance_at_least=80,
            accept_credibility_at_least=80,
        )
    )

    decision = policy.decide(
        build_event(),
        build_assessment(relevance=80, importance=80, credibility=80),
    )

    assert decision.decision is ScreeningDecisionType.ACCEPT


def test_policy_config_rejects_inconsistent_thresholds() -> None:
    with pytest.raises(ValidationError):
        ScreeningPolicyConfig(
            reject_relevance_below=71,
            accept_relevance_at_least=70,
        )
