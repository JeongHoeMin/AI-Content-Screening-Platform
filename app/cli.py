from __future__ import annotations

import argparse
import asyncio
import json
import sys
from enum import IntEnum
from pathlib import Path
from typing import Any, Sequence, Tuple

import structlog
from pydantic import ValidationError

from app.bootstrap import ExecutionMode, create_screening_workflow
from app.config import ConfigurationError
from app.models.article import Article
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
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to an Article JSON array.",
    )
    parser.add_argument("--mode", default=ExecutionMode.MOCK.value)
    return parser.parse_args(arguments)


def _configure_error_logging() -> None:
    structlog.configure(logger_factory=structlog.PrintLoggerFactory(file=sys.stderr))


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


def _serialize_result(result: ScreeningResult) -> str:
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
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def run(arguments: Sequence[str] | None = None) -> int:
    args: argparse.Namespace = parse_args(arguments)
    try:
        mode: ExecutionMode = _parse_mode(args.mode)
        articles: Tuple[Article, ...] = _load_articles(args.input)
    except CliInputError as error:
        logger.error("cli_input_failed", error_type=type(error).__name__, error=str(error))
        return int(ExitCode.INPUT_ERROR)
    try:
        workflow = create_screening_workflow(mode)
    except ConfigurationError as error:
        logger.error("cli_input_failed", error_type=type(error).__name__, error=str(error))
        return int(ExitCode.INPUT_ERROR)
    try:
        result = await workflow.run(articles)
    except Exception as error:
        logger.error(
            "cli_execution_failed",
            error_type=type(error).__name__,
            error=str(error),
        )
        return int(ExitCode.EXECUTION_ERROR)
    sys.stdout.write(_serialize_result(result))
    sys.stdout.write("\n")
    return int(ExitCode.SUCCESS)


def main(arguments: Sequence[str] | None = None) -> None:
    _configure_error_logging()
    raise SystemExit(asyncio.run(run(arguments)))


if __name__ == "__main__":
    main()
