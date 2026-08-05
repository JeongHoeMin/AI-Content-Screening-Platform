"""Harness-owned PostgreSQL storage for immutable recommendation price entries."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, Tuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_price import RecommendationPriceSnapshot
from app.persistence.schema import recommendation_price_snapshots


class SnapshotKind(str, Enum):
    """The immutable lifecycle position of a recommendation price observation."""

    ENTRY = "entry"


class RecommendationPriceEntry(BaseModel):
    """A safe persisted price record with canonical company identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot: RecommendationPriceSnapshot
    snapshot_kind: SnapshotKind = SnapshotKind.ENTRY
    company_id: str = Field(min_length=1, max_length=128)
    company_name: str = Field(min_length=1)


class RecommendationPriceRepository(Protocol):
    """Harness-owned persistence contract for immutable entry prices."""

    async def store_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        """Persist entry snapshots without replacing an existing identity."""


class SqlAlchemyRecommendationPriceRepository:
    """Persist idempotent recommendation entry snapshots with an async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def store_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        snapshot: RecommendationPriceEntry
        for snapshot in snapshots:
            price_snapshot: RecommendationPriceSnapshot = snapshot.snapshot
            await self._session.execute(
                postgresql_insert(recommendation_price_snapshots)
                .values(
                    id=str(uuid4()),
                    run_id=price_snapshot.run_id,
                    recommendation_index=price_snapshot.recommendation_index,
                    snapshot_kind=snapshot.snapshot_kind.value,
                    company_id=snapshot.company_id,
                    company_name=snapshot.company_name,
                    ticker=price_snapshot.ticker,
                    action=price_snapshot.action.value,
                    status=price_snapshot.status.value,
                    price=price_snapshot.price,
                    currency=price_snapshot.currency,
                    basis=(
                        price_snapshot.basis.value
                        if price_snapshot.basis is not None
                        else None
                    ),
                    provider=(
                        price_snapshot.provider.value
                        if price_snapshot.provider is not None
                        else None
                    ),
                    observed_at=price_snapshot.observed_at,
                    trading_date=price_snapshot.trading_date,
                    error_kind=(
                        price_snapshot.error_kind.value
                        if price_snapshot.error_kind is not None
                        else None
                    ),
                    created_at=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(
                    index_elements=["run_id", "recommendation_index", "snapshot_kind"]
                )
            )
