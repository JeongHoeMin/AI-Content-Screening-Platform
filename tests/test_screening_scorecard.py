from __future__ import annotations

from app.models.screening import (
    CredibilityScorecard,
    ImportanceScorecard,
    RelevanceScorecard,
    ScreeningScorecard,
)
from app.screeners.scorecard_policy import ScreeningScorecardPolicy


def test_scorecard_policy_calculates_equal_weighted_relevance_total() -> None:
    scorecard = ScreeningScorecard(
        relevance=RelevanceScorecard(
            theme_directness=100,
            topic_match=50,
            market_transmission_path=0,
            reason="선택 테마와 직접 연결된다.",
        ),
        importance=ImportanceScorecard(
            impact_magnitude=0,
            scope_and_spillover=0,
            time_sensitivity=0,
            reason="중요도 근거다.",
        ),
        credibility=CredibilityScorecard(
            source_authority=0,
            evidence_specificity=0,
            corroboration_and_uncertainty=0,
            reason="신뢰도 근거다.",
        ),
    )

    calculated = ScreeningScorecardPolicy().calculate(scorecard)

    assert calculated.relevance.total == 50
    assert calculated.importance.total == 0
    assert calculated.credibility.total == 0


def test_scorecard_policy_rounds_half_up() -> None:
    scorecard = ScreeningScorecard(
        relevance=RelevanceScorecard(
            theme_directness=100,
            topic_match=0,
            market_transmission_path=0,
            reason="근거",
        ),
        importance=ImportanceScorecard(
            impact_magnitude=0,
            scope_and_spillover=0,
            time_sensitivity=0,
            reason="근거",
        ),
        credibility=CredibilityScorecard(
            source_authority=0,
            evidence_specificity=0,
            corroboration_and_uncertainty=0,
            reason="근거",
        ),
    )

    calculated = ScreeningScorecardPolicy(
        relevance_weights=(0.005, 0.995, 0.0)
    ).calculate(scorecard)

    assert calculated.relevance.total == 1
