from __future__ import annotations

import json
import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

import app.bootstrap as bootstrap
from app import cli
from app.bootstrap import ExecutionMode, create_screening_workflow
from app.config import ConfigurationError, OpenAIConfig
from app.extractors import LLMNewsEventExtractor
from app.mock_grouping import build_mock_grouping_key, normalize_mock_title
from app.mock_screening import (
    DeterministicMockCrossValidator,
    DeterministicMockExtractor,
    DeterministicMockScreener,
)
from app.screeners import LLMEventScreener
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


def test_mock_bootstrap_does_not_load_openai_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_openai_config_load() -> object:
        raise AssertionError("OpenAI config must not load in mock mode")

    monkeypatch.setattr(bootstrap, "load_openai_config", fail_openai_config_load)

    workflow = bootstrap.create_screening_workflow(ExecutionMode.MOCK)

    assert workflow is not None


def test_openai_bootstrap_assembles_extractor_and_screener_as_llms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CapturingWorkflow:
        def __init__(self, **components: object) -> None:
            self.components: dict[str, object] = components

    monkeypatch.setattr(bootstrap, "ScreeningWorkflow", CapturingWorkflow)
    monkeypatch.setattr(
        bootstrap,
        "load_openai_config",
        lambda: OpenAIConfig(
            api_key="test-key",
            model="gpt-4o-mini",
            timeout_seconds=60.0,
            max_retries=2,
        ),
    )

    first = bootstrap.create_screening_workflow(ExecutionMode.OPENAI)
    second = bootstrap.create_screening_workflow(ExecutionMode.OPENAI)

    assert ExecutionMode.OPENAI in bootstrap._WORKFLOW_FACTORIES
    assert isinstance(first.components["extractor"], LLMNewsEventExtractor)
    assert isinstance(first.components["screener"], LLMEventScreener)
    assert isinstance(first.components["cross_validator"], DeterministicMockCrossValidator)
    assert first is not second


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
    ),
)
def test_cli_input_errors_write_no_stdout_and_return_exit_two(
    arguments: tuple[str, ...],
) -> None:
    result = _command("-m", "app", *arguments)

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr


def test_cli_openai_mode_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class CapturingLogger:
        def error(self, event: str, **kwargs: object) -> None:
            sys.stderr.write(f"{event}: {kwargs['error']}\n")

    def fail_workflow_factory(mode: ExecutionMode) -> object:
        raise ConfigurationError("OPENAI_API_KEY is required for openai mode.")

    monkeypatch.setattr(cli, "create_screening_workflow", fail_workflow_factory)
    monkeypatch.setattr(cli, "logger", CapturingLogger())

    exit_code: int = asyncio.run(
        cli.run(("--input", str(SAMPLE_INPUT), "--mode", "openai"))
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "OPENAI_API_KEY is required" in captured.err


def test_cli_openai_mode_rejects_blank_model(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class CapturingLogger:
        def error(self, event: str, **kwargs: object) -> None:
            sys.stderr.write(f"{event}: {kwargs['error']}\n")

    def fail_workflow_factory(mode: ExecutionMode) -> object:
        raise ConfigurationError("OPENAI_MODEL must not be empty.")

    monkeypatch.setattr(cli, "create_screening_workflow", fail_workflow_factory)
    monkeypatch.setattr(cli, "logger", CapturingLogger())

    exit_code: int = asyncio.run(
        cli.run(("--input", str(SAMPLE_INPUT), "--mode", "openai"))
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "OPENAI_MODEL must not be empty" in captured.err


def test_mock_cli_ignores_invalid_openai_environment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "   ")

    exit_code: int = asyncio.run(cli.run(("--input", str(SAMPLE_INPUT), "--mode", "mock")))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    ScreeningResult.model_validate_json(captured.out)


def test_cli_returns_execution_error_when_workflow_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FailingWorkflow:
        async def run(self, articles: tuple[Article, ...]) -> ScreeningResult:
            raise RuntimeError("all extraction batches failed")

    class CapturingLogger:
        def __init__(self) -> None:
            self.events: list[str] = []

        def error(self, event: str, **kwargs: object) -> None:
            self.events.append(event)
            sys.stderr.write(f"{event}\n")

    logger = CapturingLogger()
    monkeypatch.setattr(cli, "create_screening_workflow", lambda mode: FailingWorkflow())
    monkeypatch.setattr(cli, "logger", logger)

    exit_code: int = asyncio.run(
        cli.run(("--input", str(SAMPLE_INPUT), "--mode", "openai"))
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "cli_execution_failed" in captured.err
    assert logger.events == ["cli_execution_failed"]
