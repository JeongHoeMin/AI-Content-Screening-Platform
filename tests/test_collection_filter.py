from __future__ import annotations

from app.filters.theme_catalog import DefaultThemeCatalog
from app.filters.article_filter import ArticleFilter
from app.models.article import Article
from app.models.collection_filter import (
    CollectionFilter,
    FilterRejectionReason,
    InvestmentTheme,
    NewsTopic,
)
from datetime import datetime, timezone


def _article(article_id: str, title: str, content: str) -> Article:
    return Article(
        id=article_id,
        title=title,
        content=content,
        source="dart",
        published_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        url=f"https://example.com/{article_id}",
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


def test_catalog_does_not_match_ai_inside_an_unrelated_english_word() -> None:
    match = DefaultThemeCatalog().match(
        title="Chairman appointment announcement",
        content="The board named a new executive.",
        collection_filter=CollectionFilter(
            themes=(InvestmentTheme.ARTIFICIAL_INTELLIGENCE,),
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


def test_article_filter_preserves_matching_article_identity() -> None:
    matching = _article("dart:1", "반도체 공급 계약", "HBM 메모리 계약을 체결했다.")
    excluded = _article("dart:2", "은행 예금", "예금 금리 안내입니다.")

    result = ArticleFilter(DefaultThemeCatalog()).filter(
        (matching, excluded),
        CollectionFilter(themes=(InvestmentTheme.SEMICONDUCTOR,)),
    )

    assert result.accepted_articles == (matching,)
    assert result.rejected_article_ids == ("dart:2",)
    assert result.rejection_counts == {FilterRejectionReason.THEME_MISMATCH: 1}
    assert result.rejected_article_reasons == {
        "dart:2": FilterRejectionReason.THEME_MISMATCH
    }
