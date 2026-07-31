from __future__ import annotations

from typing import Iterator, List, Tuple

import structlog
from pydantic import ValidationError

from app.cross_validators.base import CrossValidator
from app.cross_validators.errors import NoValidCrossValidationResultsError
from app.cross_validators.parser import CrossValidationAssessmentParser
from app.cross_validators.policy import CrossValidationPolicy
from app.llms import StructuredOutputLLM
from app.llms.errors import StructuredOutputCallError, StructuredOutputResponseError
from app.llms.models import ChatMessage
from app.models.cross_validation import BatchCrossValidationConfig, CrossValidationAssessmentResponse, CrossValidationCandidate, CrossValidationParseError, CrossValidationResult
from app.prompts.base import PromptBuilder
from app.prompts.cross_validation import BatchCrossValidationPromptInput

logger = structlog.get_logger(__name__)


class LLMEventCrossValidator(CrossValidator):
    """Batches LLM evidence assessments and delegates statuses to policy."""

    def __init__(self, structured_llm: StructuredOutputLLM, parser: CrossValidationAssessmentParser, prompt_builder: PromptBuilder[BatchCrossValidationPromptInput], policy: CrossValidationPolicy, config: BatchCrossValidationConfig) -> None:
        self._structured_llm: StructuredOutputLLM = structured_llm
        self._parser: CrossValidationAssessmentParser = parser
        self._prompt_builder: PromptBuilder[BatchCrossValidationPromptInput] = prompt_builder
        self._policy: CrossValidationPolicy = policy
        self._config: BatchCrossValidationConfig = config

    async def validate(self, candidates: Tuple[CrossValidationCandidate, ...]) -> Tuple[CrossValidationResult, ...]:
        results: List[CrossValidationResult] = []
        targets: Tuple[CrossValidationCandidate, ...] = tuple(candidate for candidate in candidates if candidate.related_articles)
        results.extend(self._policy.insufficient_evidence(candidate, ("No related articles are available for cross validation.",)) for candidate in candidates if not candidate.related_articles)
        candidates_by_id: dict[str, CrossValidationCandidate] = self._index_candidates(targets)
        for batch_index, batch in enumerate(self._batches(targets)):
            try:
                parsed = await self._assess_batch(batch)
            except StructuredOutputCallError as error:
                logger.warning("cross_validation_batch_failed", batch_index=batch_index, candidate_count=len(batch), error_kind="structured_output_call", provider=error.provider, provider_error_type=error.error_type)
                if self._is_retryable_provider_error(error.error_type):
                    raise
                results.extend(
                    self._policy.insufficient_evidence(
                        candidate,
                        ("Cross-validation provider was unavailable.",),
                    )
                    for candidate in batch
                )
                continue
            except (StructuredOutputResponseError, ValidationError):
                logger.warning("cross_validation_batch_failed", batch_index=batch_index, candidate_count=len(batch), error_kind="structured_output_response")
                results.extend(
                    self._policy.insufficient_evidence(
                        candidate,
                        ("Cross-validation response could not be validated.",),
                    )
                    for candidate in batch
                )
                continue
            for error in parsed.errors:
                self._log_parse_error(batch_index, error)
            for assessment in parsed.assessments:
                candidate: CrossValidationCandidate | None = candidates_by_id.get(assessment.candidate_id)
                if candidate is None:
                    raise RuntimeError("Parsed cross-validation assessment references an unknown candidate")
                results.append(self._policy.decide(candidate, assessment))
        if targets and not any(result.event is candidate.decision.event for result in results for candidate in targets):
            raise NoValidCrossValidationResultsError("No valid cross-validation results were produced")
        results_by_event: dict[int, CrossValidationResult] = {id(result.event): result for result in results}
        return tuple(results_by_event[id(candidate.decision.event)] for candidate in candidates if id(candidate.decision.event) in results_by_event)

    @staticmethod
    def _is_retryable_provider_error(error_type: str) -> bool:
        return error_type in {
            "APITimeoutError",
            "APIConnectionError",
            "AuthenticationError",
            "PermissionDeniedError",
        }

    async def _assess_batch(self, candidates: Tuple[CrossValidationCandidate, ...]):
        messages: List[ChatMessage] = self._prompt_builder.build(BatchCrossValidationPromptInput(candidates=candidates))
        response: CrossValidationAssessmentResponse = await self._structured_llm.generate(messages=messages, response_model=CrossValidationAssessmentResponse)
        return self._parser.parse(response, candidates)

    @staticmethod
    def _index_candidates(candidates: Tuple[CrossValidationCandidate, ...]) -> dict[str, CrossValidationCandidate]:
        indexed: dict[str, CrossValidationCandidate] = {candidate.candidate_id: candidate for candidate in candidates}
        if len(indexed) != len(candidates):
            raise RuntimeError("Cross-validation candidates contain duplicate candidate IDs")
        return indexed

    @staticmethod
    def _log_parse_error(batch_index: int, error: CrossValidationParseError) -> None:
        event: str = "cross_validation_evidence_invalid" if error.evidence_index is not None else "cross_validation_candidate_invalid"
        logger.warning(event, batch_index=batch_index, event_index=error.event_index, evidence_index=error.evidence_index, candidate_id=error.candidate_id, article_id=error.article_id, error_kind=error.kind.value)

    def _batches(self, candidates: Tuple[CrossValidationCandidate, ...]) -> Iterator[Tuple[CrossValidationCandidate, ...]]:
        for index in range(0, len(candidates), self._config.max_candidates_per_batch):
            yield candidates[index:index + self._config.max_candidates_per_batch]
