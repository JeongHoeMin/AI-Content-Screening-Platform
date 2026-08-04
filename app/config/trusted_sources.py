from __future__ import annotations

import json
import os
from typing import Any, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError, model_validator

from app.config.errors import ConfigurationError


class IrRssFeedConfig(BaseModel):
    """One operator-approved corporate IR RSS or Atom feed."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, max_length=100)
    url: HttpUrl
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=200)


class TrustedSourceConfig(BaseModel):
    """Bounded settings for trusted full-text collection and preflight checks."""

    model_config = ConfigDict(frozen=True)

    ir_rss_feeds: Tuple[IrRssFeedConfig, ...] = ()
    min_body_length: int = Field(default=300, ge=1, le=100_000)
    max_body_length: int = Field(default=50_000, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def _validate_body_bounds(self) -> "TrustedSourceConfig":
        if self.min_body_length > self.max_body_length:
            raise ValueError("minimum body length cannot exceed maximum body length")
        feed_ids: Tuple[str, ...] = tuple(feed.id for feed in self.ir_rss_feeds)
        if len(feed_ids) != len(set(feed_ids)):
            raise ValueError("IR RSS feed IDs must be unique")
        return self


def load_trusted_source_config() -> TrustedSourceConfig:
    """Load safe trusted-source settings without echoing operator feed URLs."""
    raw_feeds: str = os.getenv("IR_RSS_FEEDS", "[]")
    try:
        decoded_feeds: Any = json.loads(raw_feeds)
    except json.JSONDecodeError as error:
        raise ConfigurationError("IR_RSS_FEEDS must be a JSON array") from error
    if not isinstance(decoded_feeds, list):
        raise ConfigurationError("IR_RSS_FEEDS must be a JSON array")
    try:
        return TrustedSourceConfig(
            ir_rss_feeds=tuple(decoded_feeds),
            min_body_length=os.getenv("ARTICLE_MIN_BODY_LENGTH", "300"),
            max_body_length=os.getenv("ARTICLE_MAX_BODY_LENGTH", "50000"),
        )
    except ValidationError as error:
        raise ConfigurationError("Trusted source settings are invalid") from error
