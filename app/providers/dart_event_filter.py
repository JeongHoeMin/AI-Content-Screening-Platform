from __future__ import annotations

from typing import FrozenSet, Mapping, Protocol

from app.models.dart_event_category import DartEventCategory


class DartEventTypeAllowlist(Protocol):
    """Deterministically decides whether a DART report title is worth fetching."""

    @property
    def version(self) -> str:
        """Return the stable catalog version used for matching."""

    def is_allowed(self, report_name: str) -> bool:
        """Return whether the report title matches an allowlisted event category."""


class DefaultDartEventTypeAllowlist:
    """Conservative v1 allowlist of investment-relevant DART report-title terms.

    Recurring, periodic, or low-impact disclosures (e.g. 사업보고서, 반기보고서,
    최대주주등소유주식변동신고서) are excluded by omission: only titles containing an
    allowlisted term are collected, so DART document fetches are limited to a small,
    known set of event categories instead of every disclosure in the market.
    """

    _VERSION: str = "dart-event-type-v1"
    _TERMS_BY_CATEGORY: Mapping[DartEventCategory, FrozenSet[str]] = {
        DartEventCategory.SUPPLY_CONTRACT: frozenset({"단일판매", "공급계약"}),
        DartEventCategory.EARNINGS_GUIDANCE: frozenset(
            {"실적", "가이던스", "잠정실적", "손익구조", "매출액또는손익"}
        ),
        DartEventCategory.CAPACITY_INVESTMENT: frozenset(
            {"설비투자", "신규시설투자", "증설"}
        ),
        DartEventCategory.MERGER_ACQUISITION: frozenset(
            {"합병", "타법인주식및출자증권", "영업양수", "영업양도", "지분취득"}
        ),
        DartEventCategory.CAPITAL_EVENT: frozenset(
            {
                "유상증자",
                "전환사채권발행",
                "신주인수권부사채권발행",
                "교환사채권발행",
                "자기주식취득",
                "자기주식처분",
            }
        ),
        DartEventCategory.REGULATORY_LEGAL: frozenset(
            {"소송", "제재", "행정처분", "과징금"}
        ),
    }

    @property
    def version(self) -> str:
        """Return the immutable v1 catalog identifier."""
        return self._VERSION

    def is_allowed(self, report_name: str) -> bool:
        """Return True only when the title contains an allowlisted category term."""
        normalized_title: str = report_name.strip()
        if not normalized_title:
            return False
        return any(
            term in normalized_title
            for terms in self._TERMS_BY_CATEGORY.values()
            for term in terms
        )


DEFAULT_DART_EVENT_TYPE_ALLOWLIST: DefaultDartEventTypeAllowlist = (
    DefaultDartEventTypeAllowlist()
)
