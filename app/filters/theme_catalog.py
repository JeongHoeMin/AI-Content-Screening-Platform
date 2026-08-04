from __future__ import annotations

import re
from typing import FrozenSet, Mapping, Protocol, Tuple

from app.models.collection_filter import (
    CollectionFilter,
    FilterRejectionReason,
    InvestmentTheme,
    NewsTopic,
    ThemeMatch,
)

_WHITESPACE_PATTERN: re.Pattern[str] = re.compile(r"\s+")


class ThemeCatalog(Protocol):
    """Matches normalized document text against a versioned static catalog."""

    @property
    def version(self) -> str:
        """Return the stable catalog version used for matching."""

    def match(
        self,
        *,
        title: str,
        content: str,
        collection_filter: CollectionFilter,
    ) -> ThemeMatch:
        """Return the deterministic selected-theme and selected-topic observation."""


class DefaultThemeCatalog:
    """Conservative v1 Korean and English terms for investment-theme filtering."""

    _VERSION: str = "investment-theme-v1"
    _THEME_TERMS: Mapping[InvestmentTheme, FrozenSet[str]] = {
        InvestmentTheme.SEMICONDUCTOR: frozenset(
            {"반도체", "hbm", "메모리", "semiconductor", "파운드리", "foundry", "칩", "chip"}
        ),
        InvestmentTheme.ARTIFICIAL_INTELLIGENCE: frozenset(
            {"ai", "인공지능", "생성형 ai", "llm", "gpu", "npu", "데이터센터", "data center"}
        ),
        InvestmentTheme.RENEWABLE_ENERGY: frozenset(
            {"대체에너지", "재생에너지", "태양광", "풍력", "수소", "연료전지", "renewable energy"}
        ),
    }
    _TOPIC_TERMS: Mapping[NewsTopic, FrozenSet[str]] = {
        NewsTopic.EARNINGS: frozenset(
            {"실적", "매출", "영업이익", "순이익", "가이던스", "earnings", "revenue"}
        ),
        NewsTopic.POLICY: frozenset(
            {"정책", "규제", "법안", "보조금", "policy", "regulation"}
        ),
        NewsTopic.SUPPLY_CHAIN: frozenset(
            {"공급망", "공급 계약", "수급", "납품", "supply chain", "supply agreement"}
        ),
        NewsTopic.TECHNOLOGY: frozenset(
            {"기술", "특허", "개발", "출시", "technology", "patent"}
        ),
    }

    @property
    def version(self) -> str:
        """Return the immutable v1 catalog identifier."""
        return self._VERSION

    def match(
        self,
        *,
        title: str,
        content: str,
        collection_filter: CollectionFilter,
    ) -> ThemeMatch:
        """Require every selected filter dimension while preserving match facts."""
        normalized_text: str = self._normalize_text(f"{title} {content}")
        matched_themes: Tuple[InvestmentTheme, ...] = self._matched_values(
            collection_filter.themes,
            self._THEME_TERMS,
            normalized_text,
        )
        matched_topics: Tuple[NewsTopic, ...] = self._matched_values(
            collection_filter.topics,
            self._TOPIC_TERMS,
            normalized_text,
        )
        if collection_filter.themes and not matched_themes:
            return ThemeMatch(
                accepted=False,
                rejection_reason=FilterRejectionReason.THEME_MISMATCH,
                matched_themes=matched_themes,
                matched_topics=matched_topics,
                catalog_version=self.version,
            )
        if collection_filter.topics and not matched_topics:
            return ThemeMatch(
                accepted=False,
                rejection_reason=FilterRejectionReason.TOPIC_MISMATCH,
                matched_themes=matched_themes,
                matched_topics=matched_topics,
                catalog_version=self.version,
            )
        return ThemeMatch(
            accepted=True,
            matched_themes=matched_themes,
            matched_topics=matched_topics,
            catalog_version=self.version,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return _WHITESPACE_PATTERN.sub(" ", value.lower()).strip()

    @staticmethod
    def _matched_values(
        selected_values: Tuple[InvestmentTheme, ...] | Tuple[NewsTopic, ...],
        terms_by_value: Mapping[InvestmentTheme, FrozenSet[str]]
        | Mapping[NewsTopic, FrozenSet[str]],
        normalized_text: str,
    ) -> Tuple[InvestmentTheme, ...] | Tuple[NewsTopic, ...]:
        return tuple(
            value
            for value in selected_values
            if any(
                DefaultThemeCatalog._term_matches(term, normalized_text)
                for term in terms_by_value[value]
            )
        )

    @staticmethod
    def _term_matches(term: str, normalized_text: str) -> bool:
        """Match ASCII terms as tokens while preserving Korean substring matching."""
        if not term.isascii():
            return term in normalized_text
        pattern: str = rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])"
        return re.search(pattern, normalized_text) is not None
