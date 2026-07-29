from __future__ import annotations

from typing import Iterator, List, Tuple

from app.llms import StructuredOutputLLM
from app.llms.models import ChatMessage
from app.models.llm_inference import LLMInferenceResult
from app.models.screening import (
    BatchScreeningConfig,
    ScreeningAssessment,
    ScreeningAssessmentResponse,
    ScreeningCandidate,
    ScreeningDecision,
)
from app.prompts.base import PromptBuilder
from app.prompts.screening import BatchScreeningPromptInput
from app.screeners.base import EventScreener
from app.screeners.parser import ScreeningAssessmentParser
from app.screeners.policy import ScreeningPolicy


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
        decisions: List[ScreeningDecision] = []
        for batch in self._batches(candidates):
            assessments: Tuple[ScreeningAssessment, ...] = await self._assess_batch(
                batch
            )
            decisions.extend(
                self._policy.decide(candidate.event, assessment)
                for candidate, assessment in zip(batch, assessments)
            )
        return tuple(decisions)

    async def _assess_batch(
        self,
        candidates: Tuple[ScreeningCandidate, ...],
    ) -> Tuple[ScreeningAssessment, ...]:
        prompt_input: BatchScreeningPromptInput = BatchScreeningPromptInput(
            candidates=candidates
        )
        messages: List[ChatMessage] = self._prompt_builder.build(prompt_input)
        response: ScreeningAssessmentResponse = await self._structured_llm.generate(
            messages=messages,
            response_model=ScreeningAssessmentResponse,
        )
        return self._parser.parse(response, candidates)

    def _candidates(
        self,
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
