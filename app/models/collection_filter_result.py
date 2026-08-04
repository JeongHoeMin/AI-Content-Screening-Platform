from __future__ import annotations

from datetime import datetime
from typing import Dict, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.article import Article
from app.models.collection_filter import (
    FilterRejectionReason,
    InvestmentTheme,
    NewsTopic,
)


class CollectionFilterResult(BaseModel):
    """Deterministic projection of articles accepted by a collection filter."""

    model_config = ConfigDict(frozen=True)

    accepted_articles: Tuple[Article, ...]
    rejected_article_ids: Tuple[str, ...]
    rejected_article_reasons: Dict[str, FilterRejectionReason]
    rejection_counts: Dict[FilterRejectionReason, int]
    catalog_version: str


class CollectionFilterSnapshot(BaseModel):
    """Safe, reproducible input condition snapshot for one dashboard run."""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1, max_length=64)
    themes: Tuple[InvestmentTheme, ...]
    topics: Tuple[NewsTopic, ...]
    catalog_version: str = Field(min_length=1, max_length=64)
    collected_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    rejection_counts: Dict[str, int]
    created_at: datetime

    @model_validator(mode="after")
    def _validate_counts(self) -> "CollectionFilterSnapshot":
        if self.collected_count != self.accepted_count + self.excluded_count:
            raise ValueError("Collected count must equal accepted plus excluded count")
        if any(count < 0 for count in self.rejection_counts.values()):
            raise ValueError("Filter rejection counts must not be negative")
        return self
