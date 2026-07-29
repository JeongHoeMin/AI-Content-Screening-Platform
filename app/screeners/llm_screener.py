from __future__ import annotations

from typing import Iterator, List, Tuple

import structlog
from pydantic import ValidationError

from app.llms import StructuredOutputLLM
from app.llms.errors import StructuredOutputCallError, StructuredOutputResponseError
from app.llms.models import ChatMessage
from app.models.llm_inference import LLMInferenceResult
from app.models.screening import (
    BatchScreeningConfig,
    ScreeningAssessment,
    ScreeningAssessmentResponse,
    ScreeningCandidate,
    ScreeningDecision,
    ScreeningParseError,
    ScreeningParseResult,
)
from app.prompts.base import PromptBuilder
from app.prompts.screening import BatchScreeningPromptInput
from app.screeners.base import EventScreener
from app.screeners.errors import NoValidScreeningDecisionsError
from app.screeners.parser import ScreeningAssessmentParser
from app.screeners.policy import ScreeningPolicy

logger = structlog.get_logger(__name__)


class LLMEventScreener(EventScreener):
    """Batches LLM assessments and delegates every final decision to policy."""

    def __init__(
        self,
        structured_llm: StructuredOutputLLM,
        parser: ScreeningAssessmentParser,
        prompt_builder: PromptBuilder[BatchScreeningPromptInput],
        policy: ScreeningPolicy,
        config: BatchScreeningConfig,
    ) -> None:
        self._structured_llm: StructuredOutputLLM = structured_llm
        self._parser: ScreeningAssessmentParser = parser
        self._prompt_builder: PromptBuilder[BatchScreeningPromptInput] = prompt_builder
        self._policy: ScreeningPolicy = policy
        self._config: BatchScreeningConfig = config

    async def screen(
        self,
        inferences: Tuple[LLMInferenceResult, ...],
    ) -> Tuple[ScreeningDecision, ...]:
        candidates: Tuple[ScreeningCandidate, ...] = self._candidates(inferences)
        candidates_by_id: dict[str, ScreeningCandidate] = self._index_candidates(
            candidates
        )
        decisions: List[ScreeningDecision] = []
        for batch_index, batch in enumerate(self._batches(candidates)):
            try:
                parsed: ScreeningParseResult = await self._assess_batch(batch)
            except StructuredOutputCallError:
                logger.warning(
                    "screening_batch_failed",
                    batch_index=batch_index,
                    candidate_count=len(batch),
                    error_kind="structured_output_call",
                )
                continue
            except (StructuredOutputResponseError, ValidationError):
                logger.warning(
                    "screening_batch_failed",
                    batch_index=batch_index,
                    candidate_count=len(batch),
                    error_kind="structured_output_response",
                )
                continue
            for error in parsed.errors:
                self._log_parse_error(batch_index, error)
            for assessment in parsed.assessments:
                candidate: ScreeningCandidate | None = candidates_by_id.get(
                    assessment.candidate_id
                )
                if candidate is None:
                    raise RuntimeError(
                        "Parsed screening assessment references an unknown candidate"
                    )
                decisions.append(self._policy.decide(candidate.event, assessment))
        if candidates and not decisions:
            raise NoValidScreeningDecisionsError(
                "No valid screening decisions were produced"
            )
        return tuple(decisions)

    async def _assess_batch(
        self,
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> ScreeningParseResult:
        prompt_input: BatchScreeningPromptInput = BatchScreeningPromptInput(
            candidates=candidates
        )
        messages: List[ChatMessage] = self._prompt_builder.build(prompt_input)
        response: ScreeningAssessmentResponse = await self._structured_llm.generate(
            messages=messages,
            response_model=ScreeningAssessmentResponse,
        )
        return self._parser.parse(response, candidates)

    @staticmethod
    def _index_candidates(
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> dict[str, ScreeningCandidate]:
        candidates_by_id: dict[str, ScreeningCandidate] = {
            candidate.candidate_id: candidate for candidate in candidates
        }
        if len(candidates_by_id) != len(candidates):
            raise RuntimeError("Screening candidates contain duplicate candidate IDs")
        return candidates_by_id

    @staticmethod
    def _log_parse_error(batch_index: int, error: ScreeningParseError) -> None:
        logger.warning(
            "screening_candidate_invalid",
            batch_index=batch_index,
            event_index=error.event_index,
            candidate_id=error.candidate_id,
            error_kind=error.kind.value,
        )

    @staticmethod
    def _candidates(
        inferences: Tuple[LLMInferenceResult, ...],
    ) -> Tuple[ScreeningCandidate, ...]:
        """Create request-local correlation IDs while retaining Event identity."""
        return tuple(
            ScreeningCandidate(
                candidate_id=f"{inference.article.id}:{event_index}",
                article=inference.article,
                event=event,
            )
            for inference in inferences
            for event_index, event in enumerate(inference.events)
        )

    def _batches(
        self,
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> Iterator[Tuple[ScreeningCandidate, ...]]:
        batch_size: int = self._config.max_events_per_batch
        for index in range(0, len(candidates), batch_size):
            yield candidates[index : index + batch_size]
