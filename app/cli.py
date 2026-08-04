from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from enum import IntEnum
from pathlib import Path
from datetime import timedelta
from typing import Any, List, Sequence, Tuple

import structlog
from pydantic import ValidationError

from app.bootstrap import (
    ExecutionMode,
    create_screening_workflow,
    create_screening_workflow_async,
)
from app.config import ConfigurationError
from app.harness.alerts import (
    AlertingWorkflowExecutionAuditSink,
    JsonLinesOperationalAlertSink,
    OperationalAlertPolicy,
    OperationalAlertPolicyConfig,
)
from app.harness.execution_audit import (
    JsonLinesWorkflowExecutionAuditSink,
    JsonLinesWorkflowExecutionAuditReader,
    ScreeningExecutionHarness,
    WorkflowAuditReadError,
    calculate_workflow_execution_metrics,
)
from app.models.article import Article
from app.models.collect_posts import CollectPostsRequest
from app.models.community import CommunityType
from app.market_data import (
    create_market_collect_posts_skill,
    create_market_screening_workflow,
    posts_to_articles,
)
from app.harness import Harness
from app.skills import CollectPostsSkill
from app.workflows import ScreeningResult

logger = structlog.get_logger(__name__)

_INTERNAL_RESOLUTION_FIELDS: dict[str, object] = {
    "resolved_events": {
        "__all__": {
            "companies": {
                "__all__": {
                    "company_id",
                    "resolution_status",
                    "directory_version",
                }
            }
        }
    }
}


class ExitCode(IntEnum):
    SUCCESS = 0
    EXECUTION_ERROR = 1
    INPUT_ERROR = 2


class CliInputError(ValueError):
    """Raised for invalid command-line or input-file data."""


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AI screening workflow.")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input",
        type=Path,
        help="Path to an Article JSON array.",
    )
    input_group.add_argument(
        "--audit-report",
        type=Path,
        help="Read a workflow audit JSON Lines file and emit aggregate metrics.",
    )
    input_group.add_argument(
        "--collect",
        action="store_true",
        help="Collect real Naver News and OpenDART data before screening.",
    )
    parser.add_argument("--mode", default=ExecutionMode.MOCK.value)
    parser.add_argument(
        "--sources",
        default="naver_news,dart,ir_rss",
        help="Comma-separated real collection sources for --collect.",
    )
    parser.add_argument("--category", help="Naver News search query for --collect.")
    parser.add_argument(
        "--period-hours",
        type=int,
        default=24,
        help="Positive collection lookback period in hours for --collect.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Positive per-source collection limit for --collect (maximum 100).",
    )
    parser.add_argument(
        "--audit-log",
        type=Path,
        help="Optional JSON Lines path for safe workflow execution audit records.",
    )
    parser.add_argument(
        "--alert-log",
        type=Path,
        help="Optional JSON Lines path for safe operational alerts; requires --audit-log.",
    )
    parser.add_argument(
        "--alert-max-duration-seconds",
        type=float,
        help="Optional positive duration threshold for warning alerts.",
    )
    return parser.parse_args(arguments)


def _configure_error_logging() -> None:
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
        logger_factory=structlog.PrintLoggerFactory(file=sys.__stderr__),
    )


def _parse_mode(value: str) -> ExecutionMode:
    try:
        return ExecutionMode(value)
    except ValueError as error:
        raise CliInputError(f"Unsupported execution mode: {value}") from error


def _load_articles(path: Path) -> Tuple[Article, ...]:
    try:
        with path.open("r", encoding="utf-8") as input_file:
            payload: object = json.load(input_file)
    except OSError as error:
        raise CliInputError(f"Unable to read input file: {path}") from error
    except json.JSONDecodeError as error:
        raise CliInputError(f"Input file is not valid JSON: {path}") from error
    if not isinstance(payload, list):
        raise CliInputError("Input JSON must be an array of Article objects")
    try:
        return tuple(Article.model_validate(item) for item in payload)
    except ValidationError as error:
        raise CliInputError("Input JSON contains an invalid Article") from error


def _parse_sources(value: str) -> List[CommunityType]:
    values: List[str] = [item.strip() for item in value.split(",") if item.strip()]
    if not values:
        raise CliInputError("--sources must contain at least one source")
    try:
        sources: List[CommunityType] = [CommunityType(item) for item in values]
    except ValueError as error:
        raise CliInputError("--sources contains an unsupported source") from error
    supported_sources: set[CommunityType] = {
        CommunityType.NAVER_NEWS,
        CommunityType.DART,
        CommunityType.IR_RSS,
    }
    if any(source not in supported_sources for source in sources):
        raise CliInputError("--collect supports only naver_news, dart, and ir_rss")
    return sources


def _serialize_result(
    result: ScreeningResult,
    articles: Tuple[Article, ...] = (),
) -> str:
    """Keep internal metadata and explainability fields out of the CLI schema."""
    payload: dict[str, Any] = result.model_dump(
        mode="json",
        exclude={**_INTERNAL_RESOLUTION_FIELDS, "candidate_selection": True},
    )
    payload["recommendation"] = {
        "companies": [
            {
                "score": decision.company_score.model_dump(mode="json"),
                "recommendation": decision.action.value,
            }
            for decision in result.recommendation.decisions
        ]
    }
    article_url_by_id: dict[str, str] = {
        article.id: str(article.url) for article in articles
    }
    payload["event_evidence"] = [
        {
            "event_title": decision.event.title,
            "evidence": [
                {
                    "paragraph_index": evidence.paragraph_index,
                    "quote": evidence.quote,
                    "source_url": article_url_by_id.get(evidence.article_id),
                }
                for evidence in decision.event.evidence[:2]
            ],
        }
        for decision in result.decisions
        if decision.event.evidence
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _serialize_audit_metrics(path: Path, metrics: object) -> str:
    payload: dict[str, object] = {
        "audit_log": str(path),
        "metrics": metrics,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=lambda value: value.model_dump(mode="json"))


async def run(arguments: Sequence[str] | None = None) -> int:
    _configure_error_logging()
    args: argparse.Namespace = parse_args(arguments)
    if args.audit_report is not None:
        try:
            audits = await JsonLinesWorkflowExecutionAuditReader(args.audit_report).read()
            metrics = calculate_workflow_execution_metrics(audits)
        except WorkflowAuditReadError as error:
            logger.error("cli_input_failed", error_type=type(error).__name__)
            return int(ExitCode.INPUT_ERROR)
        sys.stdout.write(_serialize_audit_metrics(args.audit_report, metrics))
        sys.stdout.write("\n")
        return int(ExitCode.SUCCESS)
    try:
        mode: ExecutionMode = _parse_mode(args.mode)
        articles: Tuple[Article, ...] = ()
        if args.alert_log is not None and args.audit_log is None:
            raise CliInputError("--alert-log requires --audit-log")
        if (
            args.alert_max_duration_seconds is not None
            and args.alert_max_duration_seconds <= 0.0
        ):
            raise CliInputError("--alert-max-duration-seconds must be positive")
        if args.collect:
            if args.period_hours <= 0 or args.limit <= 0 or args.limit > 100:
                raise CliInputError("--period-hours and --limit must be positive; limit is at most 100")
        else:
            articles = _load_articles(args.input)
    except CliInputError as error:
        logger.error("cli_input_failed", error_type=type(error).__name__)
        return int(ExitCode.INPUT_ERROR)
    collection_metadata: object = None
    try:
        if args.collect:
            sources: List[CommunityType] = _parse_sources(args.sources)
            collect_skill: CollectPostsSkill = create_market_collect_posts_skill(sources)
            collect_result = await Harness().run(
                collect_skill,
                CollectPostsRequest(
                    sources=sources,
                    limit=args.limit,
                    period=timedelta(hours=args.period_hours),
                    category=args.category,
                ),
            )
            articles = posts_to_articles(collect_result.data.posts)
            collection_metadata = {
                "collected_post_count": collect_result.metadata.collected_count,
                "article_count": len(articles),
                "error_codes": [error.code for error in collect_result.errors],
            }
            workflow = await create_market_screening_workflow(mode)
        else:
            workflow = create_screening_workflow(mode)
    except (CliInputError, ConfigurationError) as error:
        logger.error("cli_input_failed", error_type=type(error).__name__)
        return int(ExitCode.INPUT_ERROR)
    try:
        audit_sink = (
            JsonLinesWorkflowExecutionAuditSink(args.audit_log)
            if args.audit_log is not None
            else None
        )
        if args.alert_log is not None and audit_sink is not None:
            audit_sink = AlertingWorkflowExecutionAuditSink(
                audit_sink=audit_sink,
                policy=OperationalAlertPolicy(
                    OperationalAlertPolicyConfig(
                        max_duration_seconds=args.alert_max_duration_seconds,
                    )
                ),
                alert_sink=JsonLinesOperationalAlertSink(args.alert_log),
            )
        harness = ScreeningExecutionHarness(audit_sink=audit_sink)
        result = await harness.run(workflow, articles, execution_mode=mode.value)
    except Exception as error:
        logger.error(
            "cli_execution_failed",
            error_type=type(error).__name__,
        )
        return int(ExitCode.EXECUTION_ERROR)
    serialized_result: str = _serialize_result(result, articles)
    if collection_metadata is not None:
        serialized_payload: dict[str, Any] = json.loads(serialized_result)
        serialized_payload["collection"] = collection_metadata
        serialized_result = json.dumps(serialized_payload, ensure_ascii=False, indent=2)
    sys.stdout.write(serialized_result)
    sys.stdout.write("\n")
    return int(ExitCode.SUCCESS)


def main(arguments: Sequence[str] | None = None) -> None:
    _configure_error_logging()
    raise SystemExit(asyncio.run(run(arguments)))


if __name__ == "__main__":
    main()
