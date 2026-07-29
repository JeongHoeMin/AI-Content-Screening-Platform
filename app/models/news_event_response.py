from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict

from app.models.news_event import CompanyRelation


class ExtractedCompanyResponseItem(BaseModel):
    """LLM response contract for one extracted company."""

    model_config = ConfigDict(extra="forbid")

    name: str
    relation: CompanyRelation


class NewsEventResponseItem(BaseModel):
    """LLM response contract for one extracted news event."""

    model_config = ConfigDict(extra="forbid")

    title: str
    summary: str
    companies: List[ExtractedCompanyResponseItem]
    industries: List[str]
    keywords: List[str]
    reasons: List[str]


class NewsEventExtractionResponse(BaseModel):
    """Strict LLM response contract for news event extraction."""

    model_config = ConfigDict(extra="forbid")

    events: List[NewsEventResponseItem]
