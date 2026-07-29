from __future__ import annotations

import re
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.evaluators.article_evaluator import ArticleEvaluator
from app.models.article import Article, ArticleEvaluationResult, ArticleRejectReason


class RuleArticleEvaluatorConfig(BaseModel):
    """Immutable minimum validation policy for articles sent to an LLM."""

    model_config = ConfigDict(frozen=True)

    min_body_length: int = Field(default=200, gt=0)


class RuleArticleEvaluator(ArticleEvaluator):
    """Validates only whether an article is suitable to send to an LLM.

    It does not assess relevance, advertising, language, investment importance,
    or article quality beyond the configured structural minimum.
    """

    def __init__(self, config: RuleArticleEvaluatorConfig) -> None:
        self._config: RuleArticleEvaluatorConfig = config

    def evaluate(
        self,
        articles: Tuple[Article, ...],
    ) -> Tuple[ArticleEvaluationResult, ...]:
        return tuple(self._evaluate_article(article) for article in articles)

    def _evaluate_article(self, article: Article) -> ArticleEvaluationResult:
        normalized_title: str = self._normalize(article.title)
        normalized_body: str = self._normalize(article.content)
        rejection_reason: Optional[ArticleRejectReason] = self._rejection_reason(
            normalized_title,
            normalized_body,
        )
        return ArticleEvaluationResult(
            article=article,
            accepted=rejection_reason is None,
            rejection_reason=rejection_reason,
        )

    def _rejection_reason(
        self,
        normalized_title: str,
        normalized_body: str,
    ) -> Optional[ArticleRejectReason]:
        if not normalized_title:
            return ArticleRejectReason.EMPTY_TITLE
        if not normalized_body:
            return ArticleRejectReason.EMPTY_BODY
        if len(normalized_body) < self._config.min_body_length:
            return ArticleRejectReason.BODY_TOO_SHORT
        return None

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", "", value)
