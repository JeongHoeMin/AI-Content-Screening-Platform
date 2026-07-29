from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.bootstrap import ExecutionMode, create_screening_workflow
from app.mock_grouping import build_mock_grouping_key, normalize_mock_title
from app.mock_screening import DeterministicMockExtractor
from app.models import Article, CrossValidationStatus, ResolvedDecisionType
from app.workflows import ScreeningResult

PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
SAMPLE_INPUT: Path = PROJECT_ROOT / "examples" / "articles.json"


def _command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.anyio
async def test_mock_bootstrap_runs_verified_and_insufficient_evidence_paths() -> None:
    payload: object = json.loads(SAMPLE_INPUT.read_text(encoding="utf-8"))
    articles = tuple(Article.model_validate(item) for item in payload)

    result = await create_screening_workflow(ExecutionMode.MOCK).run(articles)

    assert result.statistics.resolved_accept_count == 3
    assert result.statistics.resolved_review_count == 1
    assert any(
        item.status is CrossValidationStatus.VERIFIED
        for item in result.cross_validation_results
    )
    assert any(
        item.status is CrossValidationStatus.INSUFFICIENT_EVIDENCE
        for item in result.cross_validation_results
    )
    assert any(
        item.decision is ResolvedDecisionType.ACCEPT for item in result.resolved_events
    )
    assert any(
        item.decision is ResolvedDecisionType.REVIEW for item in result.resolved_events
    )


def test_mock_grouping_normalizes_only_whitespace_and_case() -> None:
    assert (
        normalize_mock_title("  Samsung   Launches AI Chip  ")
        == "samsung launches ai chip"
    )
    assert normalize_mock_title("SAMSUNG LAUNCHES AI CHIP") == "samsung launches ai chip"
    assert (
        normalize_mock_title("Samsung, launches AI chip")
        != normalize_mock_title("Samsung launches AI chip")
    )


@pytest.mark.anyio
async def test_mock_extractor_uses_article_content_and_empty_unavailable_metadata() -> None:
    payload: object = json.loads(SAMPLE_INPUT.read_text(encoding="utf-8"))
    article: Article = Article.model_validate(payload[0])

    extraction = await DeterministicMockExtractor().extract((article,))
    event = extraction.inferences[0].events[0]

    assert event.summary == " ".join(article.content.split())[:500]
    assert event.companies == []
    assert event.industries == []
    assert event.keywords == [build_mock_grouping_key(article)]


def test_mock_bootstrap_creates_new_workflow_instances() -> None:
    first = create_screening_workflow(ExecutionMode.MOCK)
    second = create_screening_workflow(ExecutionMode.MOCK)

    assert first is not second


def test_openai_bootstrap_creates_workflow_with_configured_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    workflow = create_screening_workflow(ExecutionMode.OPENAI)

    assert isinstance(workflow, type(create_screening_workflow(ExecutionMode.MOCK)))


def test_module_and_script_entrypoints_emit_identical_json() -> None:
    module_result = _command("-m", "app", "--input", str(SAMPLE_INPUT))
    script_path: Path = Path(sys.executable).with_name("screening")
    script_result = subprocess.run(
        [str(script_path), "--input", str(SAMPLE_INPUT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert module_result.returncode == script_result.returncode == 0
    module_payload: object = json.loads(module_result.stdout)
    script_payload: object = json.loads(script_result.stdout)
    assert module_payload == script_payload
    ScreeningResult.model_validate(module_payload)


@pytest.mark.parametrize(
    "arguments",
    (
        ("--input", "missing.json"),
        ("--input", str(SAMPLE_INPUT), "--mode", "openai"),
    ),
)
def test_cli_input_errors_write_no_stdout_and_return_exit_two(
    arguments: tuple[str, ...],
) -> None:
    result = _command("-m", "app", *arguments)

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr
