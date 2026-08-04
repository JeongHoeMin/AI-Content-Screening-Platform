from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ArticleContentOrigin(str, Enum):
    """Provenance of text supplied to an LLM extraction request."""

    OFFICIAL_FULL_TEXT = "official_full_text"
    SNIPPET = "snippet"


class Article(BaseModel):
    """News article used by the news analysis domain."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    published_at: datetime
    url: HttpUrl
    content_origin: ArticleContentOrigin = ArticleContentOrigin.SNIPPET
    paragraphs: Tuple["ArticleParagraph", ...] = ()
    analysis_eligible: bool = True


class ArticleParagraph(BaseModel):
    """One numbered paragraph retained for evidence validation."""

    index: int = Field(ge=1)
    content: str = Field(min_length=1)


class ArticleRejectReason(str, Enum):
    """Reason an article is rejected before an LLM request."""

    EMPTY_TITLE = "empty_title"
    EMPTY_BODY = "empty_body"
    BODY_TOO_SHORT = "body_too_short"
    ANALYSIS_INELIGIBLE = "analysis_ineligible"


class ArticleEvaluationResult(BaseModel):
    """Immutable preflight validation result for one article."""

    model_config = ConfigDict(frozen=True)

    article: Article
    accepted: bool
    rejection_reason: Optional[ArticleRejectReason] = None

    @model_validator(mode="after")
    def _validate_rejection_contract(self) -> "ArticleEvaluationResult":
        if self.accepted and self.rejection_reason is not None:
            raise ValueError("Accepted articles cannot have a rejection reason")
        if not self.accepted and self.rejection_reason is None:
            raise ValueError("Rejected articles require a rejection reason")
        return self
