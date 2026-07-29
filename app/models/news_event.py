from __future__ import annotations

from enum import Enum
from typing import Annotated, List

from pydantic import BaseModel, Field


class CompanyRelation(str, Enum):
    """Fact-based relationship between a company and a news event."""

    DIRECT = "direct"
    INDIRECT = "indirect"


class ExtractedCompany(BaseModel):
    """Company explicitly connected to a news event."""

    name: str = Field(min_length=1)
    relation: CompanyRelation


class NewsEvent(BaseModel):
    """Non-persistent value object extracted from an evaluated article."""

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    companies: List[ExtractedCompany]
    industries: List[Annotated[str, Field(min_length=1)]]
    keywords: List[Annotated[str, Field(min_length=1)]]
    reasons: List[Annotated[str, Field(min_length=1)]]
