from __future__ import annotations

import asyncio
import os

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, async_engine_from_config
from sqlalchemy.pool import NullPool

from app.persistence.schema import metadata

config = context.config
database_url: str = os.environ.get("DATABASE_URL", "").strip()
if database_url:
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = metadata


def run_migrations_offline() -> None:
    url: str = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    """Execute Alembic migration operations through a synchronous connection facade."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async_migrations() -> None:
    """Run migrations with the application's asyncpg URL rather than a sync driver."""
    connectable: AsyncEngine = async_engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        async_connection: AsyncConnection = connection
        await async_connection.run_sync(_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Start the async migration bridge from Alembic's synchronous entrypoint."""
    asyncio.run(_run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
