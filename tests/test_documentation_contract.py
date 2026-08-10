from __future__ import annotations

from pathlib import Path


def test_workflow_docs_describe_deterministic_theme_filter() -> None:
    document: str = Path("docs/WORKFLOW.md").read_text(encoding="utf-8")

    assert "투자 테마" in document
    assert "결정적" in document
