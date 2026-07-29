from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Tuple

from app.models.recommendation import CompanyRecommendation, Recommendation
from app.models.scoring import CompanyScore, ScoringResult
from app.recommenders.recommendation_policy import RecommendationPolicy


@dataclass(frozen=True)
class RecommendationRule:
    """Read-only policy rule that decides whether it includes a score."""

    recommendation: Recommendation
    predicate: Callable[[float], bool]


def _is_strong_buy(score: float) -> bool:
    return score >= 2.0


def _is_buy(score: float) -> bool:
    return score >= 1.0


def _is_hold(score: float) -> bool:
    return score > -1.0


def _is_sell(score: float) -> bool:
    return score > -2.0


_RULES: Tuple[RecommendationRule, ...] = (
    RecommendationRule(Recommendation.STRONG_BUY, _is_strong_buy),
    RecommendationRule(Recommendation.BUY, _is_buy),
    RecommendationRule(Recommendation.HOLD, _is_hold),
    RecommendationRule(Recommendation.SELL, _is_sell),
)


@dataclass(frozen=True)
class RuleRecommendationPolicy(RecommendationPolicy):
    """Immutable deterministic policy that evaluates ordered score rules.

    Rules are evaluated from top to bottom, and the first matching rule wins.
    Their order is therefore part of the current policy.
    """

    def recommend(
        self,
        scoring: ScoringResult,
    ) -> Tuple[CompanyRecommendation, ...]:
        return tuple(
            self._recommend_company(score) for score in scoring.companies
        )

    def _recommend_company(self, score: CompanyScore) -> CompanyRecommendation:
        """Create one decision while preserving the supplied score identity."""
        return CompanyRecommendation(
            score=score,
            recommendation=self._select_recommendation(score.score),
        )

    @staticmethod
    def _select_recommendation(score: float) -> Recommendation:
        for rule in _RULES:
            if rule.predicate(score):
                return rule.recommendation
        return Recommendation.STRONG_SELL
