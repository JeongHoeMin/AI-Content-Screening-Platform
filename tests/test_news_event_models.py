from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from app.extractors import NewsEventExtractor
from app.models import (
    Article,
    ArticleEvaluationResult,
    CompanyRelation,
    NewsEvent,
    PostEvaluationResult,
)


def build_evaluation() -> ArticleEvaluationResult:
    article: Article = Article(
        id="article-1",
        title="Samsung expands HBM production",
        content="Samsung Electronics announced an expansion of HBM production.",
        source="Example News",
        published_at=datetime(2026, 7, 29, tzinfo=timezone.utc),
        url="https://example.com/articles/1",
    )
    return ArticleEvaluationResult(
        article=article,
        score=90,
        is_relevant=True,
        reasons=["Material production expansion"],
    )


class FakeNewsEventExtractor(NewsEventExtractor):
    async def extract(
        self,
        evaluation: ArticleEvaluationResult,
    ) -> List[NewsEvent]:
        return []


def test_article_evaluation_is_independent_from_post_evaluation() -> None:
    evaluation: ArticleEvaluationResult = build_evaluation()

    assert not isinstance(evaluation, PostEvaluationResult)
    assert evaluation.article.id == "article-1"


def test_company_relation_contains_only_fact_based_values() -> None:
    assert list(CompanyRelation) == [
        CompanyRelation.DIRECT,
        CompanyRelation.INDIRECT,
    ]


def test_news_event_extractor_protocol_supports_implementation() -> None:
    extractor: NewsEventExtractor = FakeNewsEventExtractor()

    assert isinstance(extractor, FakeNewsEventExtractor)
