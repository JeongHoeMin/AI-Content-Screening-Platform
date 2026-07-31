from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field

from app.models.news_event import CompanyRelation


class ExtractedCompanyResponseItem(BaseModel):
    """LLM response contract for one extracted company."""

    model_config = ConfigDict(extra="forbid")

    name: str
    relation: str


class NewsEventResponseItem(BaseModel):
    """LLM response contract for one extracted news event."""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    event_type: str
    event_facts: List[str] = Field(default_factory=list)
    companies: List[ExtractedCompanyResponseItem] = Field(default_factory=list)
    industries: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class ArticleInferenceResponseItem(BaseModel):
    """Structured LLM inference for one source article."""

    model_config = ConfigDict(extra="forbid")

    article_id: str
    summary: str = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    events: List[NewsEventResponseItem]


class NewsEventExtractionResponse(BaseModel):
    """Strict batch LLM response contract for news event extraction."""

    model_config = ConfigDict(extra="forbid")

    articles: List[ArticleInferenceResponseItem]
