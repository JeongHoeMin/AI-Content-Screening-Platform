from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.persistence import DatabaseConfig


def create_session_factory(
    config: DatabaseConfig,
) -> async_sessionmaker[AsyncSession]:
    """Create the harness-owned async database boundary from validated settings."""
    engine = create_async_engine(config.url, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False)
