from __future__ import annotations

from typing import Iterator, List, Tuple

from app.cross_validators.base import CrossValidator
from app.cross_validators.parser import CrossValidationAssessmentParser
from app.cross_validators.policy import CrossValidationPolicy
from app.llms import StructuredOutputLLM
from app.llms.models import ChatMessage
from app.models.cross_validation import (
    BatchCrossValidationConfig, CrossValidationAssessment, CrossValidationAssessmentResponse,
    CrossValidationCandidate, CrossValidationResult,
)
from app.prompts.base import PromptBuilder
from app.prompts.cross_validation import BatchCrossValidationPromptInput


class LLMCrossValidator(CrossValidator):
    def __init__(self, structured_llm: StructuredOutputLLM, parser: CrossValidationAssessmentParser, prompt_builder: PromptBuilder[BatchCrossValidationPromptInput], policy: CrossValidationPolicy, config: BatchCrossValidationConfig) -> None:
        self._structured_llm: StructuredOutputLLM = structured_llm
        self._parser: CrossValidationAssessmentParser = parser
        self._prompt_builder: PromptBuilder[BatchCrossValidationPromptInput] = prompt_builder
        self._policy: CrossValidationPolicy = policy
        self._config: BatchCrossValidationConfig = config

    async def validate(self, candidates: Tuple[CrossValidationCandidate, ...]) -> Tuple[CrossValidationResult, ...]:
        results_by_id: dict[str, CrossValidationResult] = {}
        for batch in self._batches(tuple(candidate for candidate in candidates if candidate.related_articles)):
            input_value: BatchCrossValidationPromptInput = BatchCrossValidationPromptInput(candidates=batch)
            messages: List[ChatMessage] = self._prompt_builder.build(input_value)
            response: CrossValidationAssessmentResponse = await self._structured_llm.generate(messages=messages, response_model=CrossValidationAssessmentResponse)
            assessments: Tuple[CrossValidationAssessment, ...] = self._parser.parse(response, batch)
            results_by_id.update({candidate.candidate_id: self._policy.decide(candidate, assessment) for candidate, assessment in zip(batch, assessments)})
        for candidate in candidates:
            if not candidate.related_articles:
                results_by_id[candidate.candidate_id] = self.insufficient_evidence(candidate)
        return tuple(results_by_id[candidate.candidate_id] for candidate in candidates)

    def insufficient_evidence(self, candidate: CrossValidationCandidate) -> CrossValidationResult:
        return self._policy.insufficient_evidence(candidate, ("No related articles are available for cross validation.",))

    def _batches(self, candidates: Tuple[CrossValidationCandidate, ...]) -> Iterator[Tuple[CrossValidationCandidate, ...]]:
        for index in range(0, len(candidates), self._config.max_candidates_per_batch):
            yield candidates[index:index + self._config.max_candidates_per_batch]
