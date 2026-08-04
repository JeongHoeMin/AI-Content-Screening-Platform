from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple

from app.models.screening import (
    CredibilityScorecard,
    ImportanceScorecard,
    RelevanceScorecard,
    ScreeningScorecard,
)


class ScreeningScorecardPolicy:
    """Calculate screening totals from fixed, auditable dimension weights."""

    VERSION: str = "screening-scorecard-v1"

    def __init__(
        self,
        relevance_weights: Tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3),
        importance_weights: Tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3),
        credibility_weights: Tuple[float, float, float] = (1 / 3, 1 / 3, 1 / 3),
    ) -> None:
        self._relevance_weights: Tuple[float, float, float] = self._validate_weights(
            relevance_weights
        )
        self._importance_weights: Tuple[float, float, float] = self._validate_weights(
            importance_weights
        )
        self._credibility_weights: Tuple[float, float, float] = self._validate_weights(
            credibility_weights
        )

    def calculate(self, scorecard: ScreeningScorecard) -> ScreeningScorecard:
        """Return a scorecard with all dimension totals calculated by this policy."""
        relevance: RelevanceScorecard = scorecard.relevance.model_copy(
            update={
                "total": self._weighted_total(
                    (
                        scorecard.relevance.theme_directness,
                        scorecard.relevance.topic_match,
                        scorecard.relevance.market_transmission_path,
                    ),
                    self._relevance_weights,
                )
            }
        )
        importance: ImportanceScorecard = scorecard.importance.model_copy(
            update={
                "total": self._weighted_total(
                    (
                        scorecard.importance.impact_magnitude,
                        scorecard.importance.scope_and_spillover,
                        scorecard.importance.time_sensitivity,
                    ),
                    self._importance_weights,
                )
            }
        )
        credibility: CredibilityScorecard = scorecard.credibility.model_copy(
            update={
                "total": self._weighted_total(
                    (
                        scorecard.credibility.source_authority,
                        scorecard.credibility.evidence_specificity,
                        scorecard.credibility.corroboration_and_uncertainty,
                    ),
                    self._credibility_weights,
                )
            }
        )
        return ScreeningScorecard(
            relevance=relevance,
            importance=importance,
            credibility=credibility,
        )

    @staticmethod
    def _validate_weights(
        weights: Tuple[float, float, float],
    ) -> Tuple[float, float, float]:
        if any(weight < 0.0 or weight > 1.0 for weight in weights):
            raise ValueError("Scorecard weights must be between zero and one")
        if sum(weights) != 1.0:
            raise ValueError("Scorecard weights must sum to one")
        return weights

    @staticmethod
    def _weighted_total(
        scores: Tuple[int, int, int],
        weights: Tuple[float, float, float],
    ) -> int:
        total: Decimal = sum(
            Decimal(score) * Decimal(str(weight))
            for score, weight in zip(scores, weights)
        )
        return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
