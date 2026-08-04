from __future__ import annotations

from datetime import datetime, timezone

from app.market_data import posts_to_articles
from app.models.article import ArticleContentOrigin
from app.models.community import CommunityType
from app.models.post import Post


def test_posts_to_articles_excludes_naver_discovery_result_from_analysis() -> None:
    article = posts_to_articles(
        [
            Post(
                id="naver-item",
                source=CommunityType.NAVER_NEWS,
                title="검색 결과",
                content="검색 API가 반환한 요약문입니다.",
                created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
                url="https://news.example.com/1",
            )
        ]
    )[0]

    assert article.analysis_eligible is False


def test_posts_to_articles_marks_dart_full_text_as_analysis_eligible() -> None:
    article = posts_to_articles(
        [
            Post(
                id="dart-item",
                source=CommunityType.DART,
                title="공시",
                content="공시 전문 문단입니다.",
                created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
                url="https://dart.fss.or.kr/dsaf001/main.do?rcpNo=1",
            )
        ]
    )[0]

    assert article.analysis_eligible is True


def test_posts_to_articles_preserves_ir_rss_paragraphs_as_official_full_text() -> None:
    article = posts_to_articles(
        [
            Post(
                id="ir-item",
                source=CommunityType.IR_RSS,
                title="IR 자료",
                content="첫 문단\n둘째 문단",
                paragraphs=("첫 문단", "둘째 문단"),
                created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
                url="https://ir.example.com/releases/1",
            )
        ]
    )[0]

    assert article.analysis_eligible is True
    assert article.content_origin is ArticleContentOrigin.OFFICIAL_FULL_TEXT
    assert tuple(paragraph.content for paragraph in article.paragraphs) == ("첫 문단", "둘째 문단")
