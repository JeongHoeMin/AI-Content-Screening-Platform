from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

Clock = Callable[[], datetime]


class JsonLinesRetentionPolicy(BaseModel):
    """Explicit archive-count retention policy with no implicit deletion behavior."""

    model_config = ConfigDict(frozen=True)

    max_archives: int = Field(ge=0)


class JsonLinesRotationResult(BaseModel):
    """Immutable observation of one active-log rotation attempt."""

    model_config = ConfigDict(frozen=True)

    active_path: Path
    archive_path: Optional[Path] = None
    rotated: bool


class JsonLinesPrunePlan(BaseModel):
    """Reviewable archive candidates; this model never performs deletion."""

    model_config = ConfigDict(frozen=True)

    active_path: Path
    retained_archives: Tuple[Path, ...]
    prune_candidates: Tuple[Path, ...]


class JsonLinesLogMaintenance:
    """Harness-owned safe maintenance for explicitly configured JSONL log files."""

    def __init__(
        self,
        active_path: Path,
        clock: Clock = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._active_path: Path = active_path
        self._clock: Clock = clock

    async def rotate(self) -> JsonLinesRotationResult:
        """Archive nonempty active content without overwriting any existing archive."""
        return await asyncio.to_thread(self._rotate_sync)

    async def plan_prune(self, policy: JsonLinesRetentionPolicy) -> JsonLinesPrunePlan:
        """Return only project-owned archive paths beyond the configured retention count."""
        return await asyncio.to_thread(self._plan_prune_sync, policy)

    def _rotate_sync(self) -> JsonLinesRotationResult:
        active_path: Path = self._active_path.resolve()
        if not active_path.exists():
            active_path.parent.mkdir(parents=True, exist_ok=True)
            active_path.touch(exist_ok=False)
            return JsonLinesRotationResult(active_path=active_path, rotated=False)
        if not active_path.is_file():
            raise ValueError("Active JSONL log path must be a regular file")
        if active_path.stat().st_size == 0:
            return JsonLinesRotationResult(active_path=active_path, rotated=False)
        archive_path: Path = self._archive_path_for(active_path, self._clock())
        if archive_path.exists():
            raise FileExistsError("Timestamped JSONL archive already exists")
        active_path.rename(archive_path)
        active_path.touch(exist_ok=False)
        return JsonLinesRotationResult(
            active_path=active_path,
            archive_path=archive_path,
            rotated=True,
        )

    def _plan_prune_sync(self, policy: JsonLinesRetentionPolicy) -> JsonLinesPrunePlan:
        active_path: Path = self._active_path.resolve()
        archives: Tuple[Path, ...] = self._archive_paths(active_path)
        return JsonLinesPrunePlan(
            active_path=active_path,
            retained_archives=archives[: policy.max_archives],
            prune_candidates=archives[policy.max_archives :],
        )

    def _archive_paths(self, active_path: Path) -> Tuple[Path, ...]:
        pattern: re.Pattern[str] = re.compile(
            rf"^{re.escape(active_path.stem)}\.\d{{8}}T\d{{6}}Z\.archive{re.escape(active_path.suffix)}$"
        )
        archives: list[Path] = [
            candidate.resolve()
            for candidate in active_path.parent.iterdir()
            if candidate.is_file() and pattern.fullmatch(candidate.name) is not None
        ]
        return tuple(sorted(archives, key=lambda path: path.name, reverse=True))

    def _archive_path_for(self, active_path: Path, now: datetime) -> Path:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("JSONL rotation clock must return an aware datetime")
        timestamp: str = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return active_path.with_name(
            f"{active_path.stem}.{timestamp}.archive{active_path.suffix}"
        )
