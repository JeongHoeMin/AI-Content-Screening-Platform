from __future__ import annotations

from dataclasses import dataclass

from app.models.recommendation import (
    DEFAULT_RECOMMENDATION_POLICY_CONFIG,
    RecommendationDecision,
    RecommendationPolicyConfig,
    RecommendationResult,
    RecommendationThresholdSnapshot,
)
from app.models.scoring import CompanyScore, ScoringResult
from app.recommenders.recommendation_policy import RecommendationPolicy


@dataclass(frozen=True)
class RuleRecommendationPolicy(RecommendationPolicy):
    """Deterministically creates immutable, explainable recommendation decisions."""

    config: RecommendationPolicyConfig = DEFAULT_RECOMMENDATION_POLICY_CONFIG

    def recommend(self, scoring: ScoringResult) -> RecommendationResult:
        decisions: tuple[RecommendationDecision, ...] = tuple(
            self._recommend_company(company_score)
            for company_score in scoring.companies
        )
        return RecommendationResult(
            policy_version=self.config.policy_version,
            decisions=decisions,
        )

    def _recommend_company(self, company_score: CompanyScore) -> RecommendationDecision:
        action, reason_code = RecommendationDecision._expected_evaluation(
            company_score.score,
            self.config.threshold_snapshot,
        )
        return RecommendationDecision(
            company_score=company_score,
            action=action,
            reason_code=reason_code,
            threshold_snapshot=self.config.threshold_snapshot,
        )
