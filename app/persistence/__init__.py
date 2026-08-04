"""Harness-owned PostgreSQL persistence adapters and schema."""

from app.persistence.database import create_session_factory

__all__ = ["create_session_factory"]
