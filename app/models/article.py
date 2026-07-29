from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, HttpUrl


class Article(BaseModel):
    """News article used by the news analysis domain."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    published_at: datetime
    url: HttpUrl


class ArticleEvaluationResult(BaseModel):
    """News-specific evaluation result for one article."""

    article: Article
    score: int = Field(ge=0, le=100)
    is_relevant: bool
    reasons: List[str]
