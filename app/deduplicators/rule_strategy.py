from __future__ import annotations

from dataclasses import dataclass
from typing import Set

from app.deduplicators.strategy import DuplicateStrategy
from app.models.news_event import NewsEvent


@dataclass(frozen=True)
class RuleDuplicateStrategy(DuplicateStrategy):
    """Deterministic duplicate strategy using the current default rule policy.

    This implementation does not use embeddings, semantic search, LLM
    reasoning, or machine learning models. Its comparison policy is immutable
    after construction.
    """

    keyword_similarity_threshold: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.keyword_similarity_threshold <= 1.0:
            raise ValueError(
                "keyword_similarity_threshold must be between 0.0 and 1.0"
            )

    def is_duplicate(
        self,
        left: NewsEvent,
        right: NewsEvent,
    ) -> bool:
        return (
            self._company_names(left) == self._company_names(right)
            and set(left.industries) == set(right.industries)
            and self._keyword_jaccard(left, right)
            >= self.keyword_similarity_threshold
            and self._normalize_title(left.title) == self._normalize_title(right.title)
        )

    @staticmethod
    def _company_names(event: NewsEvent) -> Set[str]:
        return {company.name for company in event.companies}

    @staticmethod
    def _keyword_jaccard(left: NewsEvent, right: NewsEvent) -> float:
        left_keywords: Set[str] = set(left.keywords)
        right_keywords: Set[str] = set(right.keywords)
        if not left_keywords and not right_keywords:
            return 1.0
        if not left_keywords or not right_keywords:
            return 0.0
        return len(left_keywords & right_keywords) / len(
            left_keywords | right_keywords
        )

    @staticmethod
    def _normalize_title(title: str) -> str:
        return " ".join(title.lower().split())
