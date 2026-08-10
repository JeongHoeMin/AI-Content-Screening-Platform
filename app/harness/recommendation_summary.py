"""Shared rendering of the safe recommendation lines sent to Telegram."""

from __future__ import annotations

from typing import Dict, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.market_prices.performance import RecommendationPerformanceItem

MAX_TELEGRAM_RECOMMENDATIONS: int = 10


class RecommendationSummaryInput(BaseModel):
    """One recommendation identity a delivery report may name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_index: int = Field(ge=0)
    company_name: str = Field(min_length=1)
    action: str = Field(min_length=1)


def build_recommendation_lines(
    recommendations: Sequence[RecommendationSummaryInput],
    performance_items: Sequence[RecommendationPerformanceItem],
    limit: int = MAX_TELEGRAM_RECOMMENDATIONS,
) -> Tuple[str, ...]:
    """Render company, action, entry price, and basis only — never provider payloads.

    Scheduled and dashboard runs report the same execution, so both paths render
    it here rather than each formatting prices their own way.
    """
    performance_by_index: Dict[int, RecommendationPerformanceItem] = {
        item.recommendation_index: item for item in performance_items
    }
    return tuple(
        _recommendation_line(
            recommendation,
            performance_by_index.get(recommendation.recommendation_index),
        )
        for recommendation in recommendations[:limit]
    )


def _recommendation_line(
    recommendation: RecommendationSummaryInput,
    performance: Optional[RecommendationPerformanceItem],
) -> str:
    """Render one line, stating plainly when no entry price was observed."""
    if (
        performance is None
        or performance.entry_price is None
        or performance.entry_basis is None
    ):
        return f"{recommendation.company_name} · {recommendation.action} · 가격 미확인 · -"
    return (
        f"{recommendation.company_name} · {recommendation.action} · "
        f"{performance.entry_price:g} KRW · {performance.entry_basis.value}"
    )
