from __future__ import annotations

from datetime import datetime, timezone

from app.models.article import Article, ArticleContentOrigin, ArticleParagraph


def test_article_preserves_numbered_full_text_paragraphs() -> None:
    article = Article(
        id="dart:1",
        title="공시",
        content="첫 문단\n둘째 문단",
        source="dart",
        published_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        url="https://dart.fss.or.kr/example",
        content_origin=ArticleContentOrigin.OFFICIAL_FULL_TEXT,
        paragraphs=(
            ArticleParagraph(index=1, content="첫 문단"),
            ArticleParagraph(index=2, content="둘째 문단"),
        ),
    )

    assert article.analysis_eligible is True
    assert article.paragraphs[1].index == 2
