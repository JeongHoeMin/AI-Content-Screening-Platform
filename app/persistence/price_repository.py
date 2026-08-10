"""Harness-owned PostgreSQL storage for immutable recommendation price entries."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Protocol, Tuple
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_price import PriceSnapshotStatus, RecommendationPriceSnapshot
from app.persistence.schema import recommendation_price_snapshots


class SnapshotKind(str, Enum):
    """The immutable lifecycle position of a recommendation price observation."""

    ENTRY = "entry"
    LATEST = "latest"


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

    async def upsert_latest(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        """Persist latest snapshots while retaining immutable entry observations."""

    async def backfill_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> int:
        """Fill in entry rows that never obtained a price, leaving priced rows alone."""

    async def list_snapshots(self) -> Tuple[RecommendationPriceEntry, ...]:
        """Load safe entry and latest observations for Harness performance evaluation."""


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
            await self._session.execute(
                postgresql_insert(recommendation_price_snapshots)
                .values(self._insert_values(snapshot))
                .on_conflict_do_nothing(
                    index_elements=["run_id", "recommendation_index", "snapshot_kind"]
                )
            )

    async def upsert_latest(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> None:
        """Upsert current observations only at their separate LATEST identities."""
        snapshot: RecommendationPriceEntry
        for snapshot in snapshots:
            if snapshot.snapshot_kind is not SnapshotKind.LATEST:
                raise ValueError("Only LATEST snapshots may be upserted")
            statement = postgresql_insert(recommendation_price_snapshots).values(
                self._insert_values(snapshot)
            )
            await self._session.execute(
                statement.on_conflict_do_update(
                    index_elements=["run_id", "recommendation_index", "snapshot_kind"],
                    set_={
                        "company_id": statement.excluded.company_id,
                        "company_name": statement.excluded.company_name,
                        "ticker": statement.excluded.ticker,
                        "action": statement.excluded.action,
                        "status": statement.excluded.status,
                        "price": statement.excluded.price,
                        "currency": statement.excluded.currency,
                        "basis": statement.excluded.basis,
                        "provider": statement.excluded.provider,
                        "observed_at": statement.excluded.observed_at,
                        "trading_date": statement.excluded.trading_date,
                        "error_kind": statement.excluded.error_kind,
                        "created_at": statement.excluded.created_at,
                    },
                )
            )

    async def backfill_entries(
        self,
        snapshots: Tuple[RecommendationPriceEntry, ...],
    ) -> int:
        """Update only entry rows still stored as UNAVAILABLE, never a priced one.

        An entry price is the immutable basis of every later return, so a
        recovered observation may replace a failed lookup but must not overwrite
        a price that was already recorded.
        """
        updated_count: int = 0
        snapshot: RecommendationPriceEntry
        for snapshot in snapshots:
            if snapshot.snapshot_kind is not SnapshotKind.ENTRY:
                raise ValueError("Only ENTRY snapshots may be backfilled")
            price_snapshot: RecommendationPriceSnapshot = snapshot.snapshot
            result = await self._session.execute(
                update(recommendation_price_snapshots)
                .where(
                    recommendation_price_snapshots.c.run_id == price_snapshot.run_id,
                    recommendation_price_snapshots.c.recommendation_index
                    == price_snapshot.recommendation_index,
                    recommendation_price_snapshots.c.snapshot_kind
                    == SnapshotKind.ENTRY.value,
                    recommendation_price_snapshots.c.status
                    == PriceSnapshotStatus.UNAVAILABLE.value,
                )
                .values(
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
                )
            )
            updated_count += result.rowcount or 0
        return updated_count

    async def list_snapshots(self) -> Tuple[RecommendationPriceEntry, ...]:
        """Read only validated price columns, ordered for deterministic projections."""
        result = await self._session.execute(
            select(recommendation_price_snapshots).order_by(
                recommendation_price_snapshots.c.run_id,
                recommendation_price_snapshots.c.recommendation_index,
                recommendation_price_snapshots.c.snapshot_kind,
            )
        )
        rows: Tuple[Mapping[str, object], ...] = tuple(result.mappings().all())
        return tuple(self._entry_from_row(row) for row in rows)

    @staticmethod
    def _insert_values(snapshot: RecommendationPriceEntry) -> dict[str, object]:
        """Build one explicit safe persistence mapping from a validated entry."""
        price_snapshot: RecommendationPriceSnapshot = snapshot.snapshot
        return {
            "id": str(uuid4()),
            "run_id": price_snapshot.run_id,
            "recommendation_index": price_snapshot.recommendation_index,
            "snapshot_kind": snapshot.snapshot_kind.value,
            "company_id": snapshot.company_id,
            "company_name": snapshot.company_name,
            "ticker": price_snapshot.ticker,
            "action": price_snapshot.action.value,
            "status": price_snapshot.status.value,
            "price": price_snapshot.price,
            "currency": price_snapshot.currency,
            "basis": price_snapshot.basis.value if price_snapshot.basis is not None else None,
            "provider": (
                price_snapshot.provider.value if price_snapshot.provider is not None else None
            ),
            "observed_at": price_snapshot.observed_at,
            "trading_date": price_snapshot.trading_date,
            "error_kind": (
                price_snapshot.error_kind.value
                if price_snapshot.error_kind is not None
                else None
            ),
            "created_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def _entry_from_row(row: Mapping[str, object]) -> RecommendationPriceEntry:
        """Rehydrate persisted safe columns through the immutable domain validator."""
        return RecommendationPriceEntry(
            snapshot=RecommendationPriceSnapshot(
                run_id=str(row["run_id"]),
                recommendation_index=int(row["recommendation_index"]),
                ticker=str(row["ticker"]),
                action=str(row["action"]),
                status=str(row["status"]),
                price=row["price"],
                currency=str(row["currency"]),
                basis=row["basis"],
                provider=row["provider"],
                observed_at=row["observed_at"],
                trading_date=row["trading_date"],
                error_kind=row["error_kind"],
            ),
            snapshot_kind=SnapshotKind(str(row["snapshot_kind"])),
            company_id=str(row["company_id"]),
            company_name=str(row["company_name"]),
        )
