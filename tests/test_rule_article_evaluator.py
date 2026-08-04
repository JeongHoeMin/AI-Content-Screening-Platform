from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from app.evaluators import RuleArticleEvaluator, RuleArticleEvaluatorConfig
from app.models import Article, ArticleRejectReason


def build_article(title: str, content: str) -> Article:
    return Article(
        id="article-1",
        title=title,
        content=content,
        source="Example News",
        published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url="https://example.com/articles/1",
    )


def test_evaluator_accepts_whitespace_normalized_content_at_configured_boundary() -> None:
    article: Article = build_article("Title", "a \n" * 100)
    evaluator: RuleArticleEvaluator = RuleArticleEvaluator(
        RuleArticleEvaluatorConfig(min_body_length=100)
    )

    result = evaluator.evaluate((article,))

    assert result[0].accepted is True
    assert result[0].rejection_reason is None
    assert result[0].article is article


def test_evaluator_applies_rejection_priority() -> None:
    article: Article = build_article("   ", "   ")
    evaluator: RuleArticleEvaluator = RuleArticleEvaluator(
        RuleArticleEvaluatorConfig(min_body_length=200)
    )

    result = evaluator.evaluate((article,))

    assert result[0].accepted is False
    assert result[0].rejection_reason is ArticleRejectReason.EMPTY_TITLE


def test_evaluator_rejects_empty_and_short_bodies() -> None:
    empty_body: Article = build_article("Title", "   ")
    short_body: Article = build_article("Title", "short")
    evaluator: RuleArticleEvaluator = RuleArticleEvaluator(
        RuleArticleEvaluatorConfig(min_body_length=10)
    )

    result = evaluator.evaluate((empty_body, short_body))

    assert tuple(item.rejection_reason for item in result) == (
        ArticleRejectReason.EMPTY_BODY,
        ArticleRejectReason.BODY_TOO_SHORT,
    )


def test_evaluator_rejects_discovery_only_article_before_llm_input() -> None:
    article: Article = build_article("Title", "본문 " * 100).model_copy(
        update={"analysis_eligible": False}
    )
    evaluator: RuleArticleEvaluator = RuleArticleEvaluator(
        RuleArticleEvaluatorConfig(min_body_length=10)
    )

    result = evaluator.evaluate((article,))

    assert result[0].accepted is False
    assert result[0].rejection_reason is ArticleRejectReason.ANALYSIS_INELIGIBLE
