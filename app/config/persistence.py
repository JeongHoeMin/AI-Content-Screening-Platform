from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from app.config.errors import ConfigurationError


@dataclass(frozen=True)
class DatabaseConfig:
    """Validated asynchronous PostgreSQL connection configuration."""

    url: str

    def __repr__(self) -> str:
        parsed = urlsplit(self.url)
        hostname: str = parsed.hostname or ""
        port: str = f":{parsed.port}" if parsed.port is not None else ""
        username: str = f"{parsed.username}@" if parsed.username else ""
        safe_netloc: str = f"{username}{hostname}{port}"
        safe_url: str = urlunsplit(
            (parsed.scheme, safe_netloc, parsed.path, parsed.query, parsed.fragment)
        )
        return f"DatabaseConfig(url={safe_url!r})"


def load_database_config() -> DatabaseConfig:
    """Load the required asyncpg PostgreSQL URL without leaking credentials."""
    url: str = os.environ.get("DATABASE_URL", "").strip()
    if not url.startswith("postgresql+asyncpg://"):
        raise ConfigurationError("DATABASE_URL must use postgresql+asyncpg://")
    return DatabaseConfig(url=url)


def load_optional_database_config() -> Optional[DatabaseConfig]:
    """Load database settings only when persistence is configured for this run."""
    if not os.environ.get("DATABASE_URL", "").strip():
        return None
    return load_database_config()
