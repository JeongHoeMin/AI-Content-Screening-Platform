from __future__ import annotations

from math import inf, nan

import pytest
from pydantic import ValidationError

from app.models import (
    DEFAULT_DIRECTION_SCORE_CATALOG,
    DEFAULT_SCORING_POLICY_CONFIG,
    CompanyImpact,
    CompanyRelation,
    CompanyScore,
    DirectionScoreCatalog,
    DirectionScoreEntry,
    ImpactDirection,
    ResolvedCompany,
    ResolvedTicker,
    ScoreContribution,
    ScoreFactor,
    ScoreReasonCode,
    ScoringPolicyConfig,
)


def build_company() -> ResolvedCompany:
    return ResolvedCompany(name="Company", relation=CompanyRelation.DIRECT, ticker=ResolvedTicker(ticker="005930", exchange="KRX"))


def build_contribution(value: float = 1.0) -> ScoreContribution:
    company: ResolvedCompany = build_company()
    return ScoreContribution(
        impact=CompanyImpact(company=company, direction=ImpactDirection.POSITIVE),
        factor=ScoreFactor.POSITIVE_EVIDENCE,
        weight=value,
        value=value,
        reason_code=ScoreReasonCode.POSITIVE_DIRECTION_WEIGHT,
    )


def test_default_catalog_contains_the_approved_mapping_for_every_direction() -> None:
    assert {
        entry.direction: (entry.factor, entry.weight, entry.reason_code)
        for entry in DEFAULT_DIRECTION_SCORE_CATALOG.entries
    } == {
        ImpactDirection.POSITIVE: (ScoreFactor.POSITIVE_EVIDENCE, 1.0, ScoreReasonCode.POSITIVE_DIRECTION_WEIGHT),
        ImpactDirection.NEGATIVE: (ScoreFactor.NEGATIVE_EVIDENCE, -1.0, ScoreReasonCode.NEGATIVE_DIRECTION_WEIGHT),
        ImpactDirection.NEUTRAL: (ScoreFactor.NON_DIRECTIONAL_EVIDENCE, 0.0, ScoreReasonCode.NEUTRAL_DIRECTION_WEIGHT),
        ImpactDirection.UNKNOWN: (ScoreFactor.NON_DIRECTIONAL_EVIDENCE, 0.0, ScoreReasonCode.UNKNOWN_DIRECTION_WEIGHT),
    }


def test_catalog_rejects_duplicate_and_missing_directions() -> None:
    duplicate_entries = DEFAULT_DIRECTION_SCORE_CATALOG.entries + (
        DEFAULT_DIRECTION_SCORE_CATALOG.entries[0],
    )
    with pytest.raises(ValidationError, match="Duplicate directions: POSITIVE"):
        DirectionScoreCatalog(entries=duplicate_entries)

    missing_entries = tuple(
        entry for entry in DEFAULT_DIRECTION_SCORE_CATALOG.entries
        if entry.direction is not ImpactDirection.UNKNOWN
    )
    with pytest.raises(ValidationError, match="Missing directions: UNKNOWN"):
        DirectionScoreCatalog(entries=missing_entries)


@pytest.mark.parametrize("weight", [nan, inf, -inf])
def test_entry_rejects_non_finite_weight(weight: float) -> None:
    with pytest.raises(ValidationError, match="finite"):
        DirectionScoreEntry(direction=ImpactDirection.POSITIVE, factor=ScoreFactor.POSITIVE_EVIDENCE, weight=weight, reason_code=ScoreReasonCode.POSITIVE_DIRECTION_WEIGHT)


def test_config_rejects_blank_version_and_catalog_weight_outside_range() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        ScoringPolicyConfig(policy_version=" ", min_weight=-1.0, max_weight=1.0, catalog=DEFAULT_DIRECTION_SCORE_CATALOG)

    with pytest.raises(ValidationError, match="Directions: NEGATIVE"):
        ScoringPolicyConfig(policy_version="v1", min_weight=-0.5, max_weight=1.0, catalog=DEFAULT_DIRECTION_SCORE_CATALOG)


def test_contribution_and_company_score_enforce_atomic_provenance() -> None:
    contribution: ScoreContribution = build_contribution()
    company_score: CompanyScore = CompanyScore(company=contribution.impact.company, score=1.0, contributions=(contribution,))

    assert company_score.evidences == (contribution.impact,)
    assert company_score.evidences[0] is contribution.impact
    with pytest.raises(ValidationError, match="value must equal weight"):
        ScoreContribution(impact=contribution.impact, factor=contribution.factor, weight=1.0, value=0.5, reason_code=contribution.reason_code)
    with pytest.raises(ValidationError, match="sum of contribution"):
        CompanyScore(company=contribution.impact.company, score=0.0, contributions=(contribution,))
    with pytest.raises(ValidationError, match="Extra inputs"):
        CompanyScore(company=contribution.impact.company, score=1.0, contributions=(contribution,), evidences=())


def test_default_config_is_the_single_bootstrap_policy_value() -> None:
    assert DEFAULT_SCORING_POLICY_CONFIG.catalog is DEFAULT_DIRECTION_SCORE_CATALOG
