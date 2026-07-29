from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from app.analyzers.strategy import ImpactStrategy
from app.models.impact_analysis import CompanyImpact, ImpactDirection
from app.models.resolved_news_event import ResolvedNewsEvent

_POSITIVE_RULES: Tuple[str, ...] = (
    "공장 증설",
    "설비 투자",
    "투자 확대",
)
_NEGATIVE_RULES: Tuple[str, ...] = (
    "소송",
    "리콜",
    "계약 종료",
)


@dataclass(frozen=True)
class RuleImpactStrategy(ImpactStrategy):
    """Immutable deterministic strategy using the current default rule policy.

    This implementation concatenates title and summary before applying keyword
    rules. It does not use LLMs, embeddings, APIs, databases, or confidence
    calculations.
    """

    def analyze(self, event: ResolvedNewsEvent) -> Tuple[CompanyImpact, ...]:
        direction: ImpactDirection = self._determine_direction(event)
        return tuple(
            CompanyImpact(company=company, direction=direction)
            for company in event.companies
        )

    @staticmethod
    def _determine_direction(event: ResolvedNewsEvent) -> ImpactDirection:
        text: str = f"{event.event.title}\n{event.event.summary}"
        has_positive: bool = any(rule in text for rule in _POSITIVE_RULES)
        has_negative: bool = any(rule in text for rule in _NEGATIVE_RULES)
        if has_positive == has_negative:
            return ImpactDirection.UNKNOWN
        if has_positive:
            return ImpactDirection.POSITIVE
        return ImpactDirection.NEGATIVE
