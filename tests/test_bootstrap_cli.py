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
from app.cross_validators import LLMEventCrossValidator
from app.models import (
    DEFAULT_RANKING_POLICY_CONFIG,
    DEFAULT_SCORING_POLICY_CONFIG,
    Article,
    CrossValidationStatus,
    ResolvedDecisionType,
)
from app.scorers import EvidenceAwareScoringStrategy
from app.candidates import DefaultCandidateSelectionEngine, RuleCandidateSelectionPolicy
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


def test_bootstrap_reuses_the_default_scoring_config_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CapturingWorkflow:
        def __init__(self, **components: object) -> None:
            self.components: dict[str, object] = components

    monkeypatch.setattr(bootstrap, "ScreeningWorkflow", CapturingWorkflow)
    workflow = bootstrap.create_screening_workflow(ExecutionMode.MOCK)
    scoring_engine = workflow.components["scoring_engine"]
    strategy = scoring_engine._strategy

    assert isinstance(strategy, EvidenceAwareScoringStrategy)
    assert strategy.config is DEFAULT_SCORING_POLICY_CONFIG


def test_bootstrap_reuses_the_default_ranking_config_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CapturingWorkflow:
        def __init__(self, **components: object) -> None:
            self.components: dict[str, object] = components

    monkeypatch.setattr(bootstrap, "ScreeningWorkflow", CapturingWorkflow)
    workflow = bootstrap.create_screening_workflow(ExecutionMode.MOCK)
    candidate_selection_engine = workflow.components["candidate_selection_engine"]

    assert isinstance(candidate_selection_engine, DefaultCandidateSelectionEngine)
    policy = candidate_selection_engine._policy
    assert isinstance(policy, RuleCandidateSelectionPolicy)
    assert policy.config is DEFAULT_RANKING_POLICY_CONFIG


def test_mock_bootstrap_does_not_load_openai_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_openai_config_load() -> object:
        raise AssertionError("OpenAI config must not load in mock mode")

    monkeypatch.setattr(bootstrap, "load_openai_config", fail_openai_config_load)

    workflow = bootstrap.create_screening_workflow(ExecutionMode.MOCK)

    assert workflow is not None


def test_openai_bootstrap_assembles_llm_pipeline_components(
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
    assert isinstance(first.components["cross_validator"], LLMEventCrossValidator)
    assert (
        first.components["extractor"]._structured_llm
        is first.components["screener"]._structured_llm
    )
    assert first.components["screener"]._structured_llm is first.components["cross_validator"]._structured_llm
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
    assert "candidate_selection" not in module_payload
    assert "companies" in module_payload["recommendation"]


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
    payload: object = json.loads(captured.out)
    assert "candidate_selection" not in payload
    assert "companies" in payload["recommendation"]


def test_mock_cli_writes_opt_in_safe_execution_audit(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    audit_path: Path = tmp_path / "workflow-audit.jsonl"

    exit_code: int = asyncio.run(
        cli.run(("--input", str(SAMPLE_INPUT), "--mode", "mock", "--audit-log", str(audit_path)))
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out)["recommendation"]
    lines: list[str] = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    audit: dict[str, object] = json.loads(lines[0])
    assert audit["execution_mode"] == "mock"
    assert audit["status"] == "succeeded"
    assert "statistics" in audit
    assert "Samsung" not in lines[0]


def test_mock_cli_writes_duration_alert_to_opt_in_alert_log(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    audit_path: Path = tmp_path / "workflow-audit.jsonl"
    alert_path: Path = tmp_path / "workflow-alert.jsonl"

    exit_code: int = asyncio.run(
        cli.run(
            (
                "--input", str(SAMPLE_INPUT), "--audit-log", str(audit_path),
                "--alert-log", str(alert_path), "--alert-max-duration-seconds", "0.000001",
            )
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out)["recommendation"]
    alert: dict[str, object] = json.loads(alert_path.read_text(encoding="utf-8"))
    assert alert["alert_type"] == "duration_exceeded"
    assert alert["severity"] == "warning"
    assert "Samsung" not in alert_path.read_text(encoding="utf-8")


def test_cli_rejects_alert_log_without_audit_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    alert_path: Path = tmp_path / "workflow-alert.jsonl"

    class CapturingLogger:
        def error(self, event: str, **kwargs: object) -> None:
            return None

    monkeypatch.setattr(cli, "logger", CapturingLogger())

    exit_code: int = asyncio.run(
        cli.run(("--input", str(SAMPLE_INPUT), "--alert-log", str(alert_path)))
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert not alert_path.exists()


def test_cli_audit_report_reads_metrics_without_running_workflow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    audit_path: Path = tmp_path / "workflow-audit.jsonl"
    audit_path.write_text(
        json.dumps(
            {
                "execution_id": "execution-1",
                "execution_mode": "mock",
                "status": "failed",
                "started_at": "2026-07-30T00:00:00Z",
                "finished_at": "2026-07-30T00:00:02Z",
                "duration_seconds": 2.0,
                "input_article_count": 4,
                "error_type": "RuntimeError",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fail_workflow_factory(mode: ExecutionMode) -> object:
        raise AssertionError("audit report must not create a workflow")

    monkeypatch.setattr(cli, "create_screening_workflow", fail_workflow_factory)
    exit_code: int = asyncio.run(cli.run(("--audit-report", str(audit_path))))
    captured = capsys.readouterr()

    assert exit_code == 0
    payload: dict[str, object] = json.loads(captured.out)
    assert payload["audit_log"] == str(audit_path)
    metrics: dict[str, object] = payload["metrics"]
    assert metrics["total_executions"] == 1
    assert metrics["failed_executions"] == 1
    assert metrics["total_input_articles"] == 4


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
