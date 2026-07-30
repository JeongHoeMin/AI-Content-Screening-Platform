from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.bootstrap import ExecutionMode, create_screening_workflow
from app.harness.execution_audit import JsonLinesWorkflowExecutionAuditSink, ScreeningExecutionHarness
from app.models.article import Article
from app.workflows import WorkflowProgressEvent


PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]


def test_live_progress_emits_completed_langgraph_nodes_and_writes_audit(tmp_path: Path) -> None:
    payload: object = json.loads(
        (PROJECT_ROOT / "examples" / "articles.json").read_text(encoding="utf-8")
    )
    articles: tuple[Article, ...] = tuple(Article.model_validate(item) for item in payload)
    events: list[WorkflowProgressEvent] = []

    async def record(event: WorkflowProgressEvent) -> None:
        events.append(event)

    audit_path: Path = tmp_path / "audit.jsonl"
    result = asyncio.run(
        ScreeningExecutionHarness(JsonLinesWorkflowExecutionAuditSink(audit_path)).run_with_progress(
            create_screening_workflow(ExecutionMode.MOCK),
            articles,
            ExecutionMode.MOCK.value,
            record,
        )
    )

    assert [event.node for event in events] == [
        "evaluate",
        "extract",
        "screen",
        "cross_validate",
        "resolve",
        "analyze",
        "aggregate",
        "score",
        "recommend",
        "select_candidates",
    ]
    assert [event.completed_node_count for event in events] == list(range(1, 11))
    assert result.statistics.total_articles == len(articles)
    assert len(audit_path.read_text(encoding="utf-8").splitlines()) == 1
