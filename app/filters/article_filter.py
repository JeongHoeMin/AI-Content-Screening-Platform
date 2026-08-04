from __future__ import annotations

from collections import Counter
from typing import Dict, Sequence, Tuple

from app.filters.theme_catalog import ThemeCatalog
from app.models.article import Article
from app.models.collection_filter import CollectionFilter, FilterRejectionReason
from app.models.collection_filter_result import CollectionFilterResult


class ArticleFilter:
    """Apply a deterministic investment-theme filter without changing articles."""

    def __init__(self, catalog: ThemeCatalog) -> None:
        self._catalog: ThemeCatalog = catalog

    def filter(
        self,
        articles: Sequence[Article],
        collection_filter: CollectionFilter,
    ) -> CollectionFilterResult:
        """Return matching original article instances and safe exclusion observations."""
        accepted_articles: list[Article] = []
        rejected_article_ids: list[str] = []
        rejected_article_reasons: Dict[str, FilterRejectionReason] = {}
        rejection_counts: Counter[FilterRejectionReason] = Counter()
        for article in articles:
            match = self._catalog.match(
                title=article.title,
                content=article.content,
                collection_filter=collection_filter,
            )
            if match.accepted:
                accepted_articles.append(article)
                continue
            if match.rejection_reason is None:
                raise ValueError("Rejected collection filter match requires a rejection reason")
            rejected_article_ids.append(article.id)
            rejected_article_reasons[article.id] = match.rejection_reason
            rejection_counts[match.rejection_reason] += 1
        counts: Dict[FilterRejectionReason, int] = dict(rejection_counts)
        return CollectionFilterResult(
            accepted_articles=tuple(accepted_articles),
            rejected_article_ids=tuple(rejected_article_ids),
            rejected_article_reasons=rejected_article_reasons,
            rejection_counts=counts,
            catalog_version=self._catalog.version,
        )
