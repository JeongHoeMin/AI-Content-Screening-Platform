from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.persistence import DatabaseConfig
from app.persistence.database import create_session_factory


def test_create_session_factory_uses_validated_async_database_url() -> None:
    session_factory = create_session_factory(
        DatabaseConfig(url="postgresql+asyncpg://screening:secret@db:5432/screening")
    )

    session = session_factory()

    assert isinstance(session, AsyncSession)
    assert session.bind is not None
    assert str(session.bind.url).startswith("postgresql+asyncpg://screening:")
