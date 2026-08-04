from __future__ import annotations

from typing import Dict, Tuple

from pydantic import BaseModel, ConfigDict

from app.models.article import Article
from app.models.collection_filter import FilterRejectionReason


class CollectionFilterResult(BaseModel):
    """Deterministic projection of articles accepted by a collection filter."""

    model_config = ConfigDict(frozen=True)

    accepted_articles: Tuple[Article, ...]
    rejected_article_ids: Tuple[str, ...]
    rejected_article_reasons: Dict[str, FilterRejectionReason]
    rejection_counts: Dict[FilterRejectionReason, int]
    catalog_version: str
