from __future__ import annotations

from typing import Protocol, Tuple

from app.models.article import Article, ArticleEvaluationResult


class ArticleEvaluator(Protocol):
    """Performs preflight validation before articles reach an LLM."""

    def evaluate(
        self,
        articles: Tuple[Article, ...],
    ) -> Tuple[ArticleEvaluationResult, ...]:
        """Return one immutable validation result for each input article."""
        ...
