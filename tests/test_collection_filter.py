from __future__ import annotations

from app.filters.theme_catalog import DefaultThemeCatalog
from app.models.collection_filter import (
    CollectionFilter,
    FilterRejectionReason,
    InvestmentTheme,
    NewsTopic,
)


def test_catalog_requires_theme_and_topic_when_both_are_selected() -> None:
    match = DefaultThemeCatalog().match(
        title="AI 서버용 HBM 공급 확대",
        content="메모리 반도체 수요가 증가했다.",
        collection_filter=CollectionFilter(
            themes=(InvestmentTheme.SEMICONDUCTOR,),
            topics=(NewsTopic.EARNINGS,),
        ),
    )

    assert match.accepted is False
    assert match.rejection_reason is FilterRejectionReason.TOPIC_MISMATCH


def test_catalog_accepts_empty_filter_without_keyword_match() -> None:
    match = DefaultThemeCatalog().match(
        title="일반 금융 공시",
        content="예금 금리 안내입니다.",
        collection_filter=CollectionFilter(),
    )

    assert match.accepted is True
    assert match.matched_themes == ()
    assert match.matched_topics == ()
    assert match.catalog_version == "investment-theme-v1"


def test_catalog_rejects_selected_theme_without_theme_term() -> None:
    match = DefaultThemeCatalog().match(
        title="은행 예금 상품",
        content="예금 금리 안내입니다.",
        collection_filter=CollectionFilter(
            themes=(InvestmentTheme.SEMICONDUCTOR,),
        ),
    )

    assert match.accepted is False
    assert match.rejection_reason is FilterRejectionReason.THEME_MISMATCH


def test_collection_filter_deduplicates_selected_values_in_input_order() -> None:
    collection_filter = CollectionFilter(
        themes=(
            InvestmentTheme.SEMICONDUCTOR,
            InvestmentTheme.SEMICONDUCTOR,
            InvestmentTheme.ARTIFICIAL_INTELLIGENCE,
        ),
        topics=(NewsTopic.TECHNOLOGY, NewsTopic.TECHNOLOGY),
    )

    assert collection_filter.themes == (
        InvestmentTheme.SEMICONDUCTOR,
        InvestmentTheme.ARTIFICIAL_INTELLIGENCE,
    )
    assert collection_filter.topics == (NewsTopic.TECHNOLOGY,)
