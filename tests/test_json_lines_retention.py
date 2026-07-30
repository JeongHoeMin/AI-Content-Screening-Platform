from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.harness.retention import JsonLinesLogMaintenance, JsonLinesRetentionPolicy


@pytest.mark.anyio
async def test_rotation_archives_nonempty_log_without_overwriting_and_recreates_active(
    tmp_path: Path,
) -> None:
    active_path: Path = tmp_path / "workflow-audit.jsonl"
    active_path.write_text('{"execution_id":"safe"}\n', encoding="utf-8")
    maintenance: JsonLinesLogMaintenance = JsonLinesLogMaintenance(
        active_path,
        clock=lambda: datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc),
    )

    result = await maintenance.rotate()

    assert result.rotated is True
    assert result.archive_path == tmp_path / "workflow-audit.20260730T120000Z.archive.jsonl"
    assert result.archive_path.read_text(encoding="utf-8") == '{"execution_id":"safe"}\n'
    assert active_path.read_text(encoding="utf-8") == ""


@pytest.mark.anyio
async def test_rotation_is_noop_for_empty_active_log(tmp_path: Path) -> None:
    active_path: Path = tmp_path / "workflow-audit.jsonl"
    active_path.touch()

    result = await JsonLinesLogMaintenance(active_path).rotate()

    assert result.rotated is False
    assert result.archive_path is None


@pytest.mark.anyio
async def test_prune_plan_keeps_newest_project_archives_without_deleting_files(
    tmp_path: Path,
) -> None:
    active_path: Path = tmp_path / "workflow-audit.jsonl"
    for timestamp in ("20260728T120000Z", "20260729T120000Z", "20260730T120000Z"):
        (tmp_path / f"workflow-audit.{timestamp}.archive.jsonl").write_text(
            "{}\n", encoding="utf-8"
        )
    unrelated: Path = tmp_path / "workflow-audit.backup.jsonl"
    unrelated.write_text("keep", encoding="utf-8")
    maintenance: JsonLinesLogMaintenance = JsonLinesLogMaintenance(active_path)

    plan = await maintenance.plan_prune(JsonLinesRetentionPolicy(max_archives=2))

    assert [path.name for path in plan.retained_archives] == [
        "workflow-audit.20260730T120000Z.archive.jsonl",
        "workflow-audit.20260729T120000Z.archive.jsonl",
    ]
    assert [path.name for path in plan.prune_candidates] == [
        "workflow-audit.20260728T120000Z.archive.jsonl"
    ]
    assert plan.prune_candidates[0].exists()
    assert unrelated.exists()
