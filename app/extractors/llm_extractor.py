from __future__ import annotations

from typing import Iterator, List, Tuple

from pydantic import ValidationError

from app.extractors.base import NewsEventExtractor
from app.extractors.errors import AllExtractionBatchesFailedError
from app.extractors.errors import InferenceResultValidationError
from app.llms.openai_structured import StructuredOutputResponseError
from app.extractors.parser import NewsEventParser
from app.llms import StructuredOutputLLM
from app.llms.models import ChatMessage
from app.models.article import Article
from app.models.llm_inference import (
    BatchExtractionConfig,
    ExtractionError,
    ExtractionErrorKind,
    LLMExtractionResult,
    LLMInferenceResult,
    NewsEventParseResult,
)
from app.models.news_event_response import NewsEventExtractionResponse
from app.prompts.base import PromptBuilder
from app.prompts.news_event import BatchNewsEventPromptInput


class LLMNewsEventExtractor(NewsEventExtractor):
    """Extracts batch inferences through injected prompt, LLM, and parser contracts.

    Prompt creation belongs solely to the injected PromptBuilder. This class
    owns batch orchestration and delegates typed output generation to
    StructuredOutputLLM and event validation to NewsEventParser.
    """

    def __init__(
        self,
        structured_llm: StructuredOutputLLM,
        parser: NewsEventParser,
        prompt_builder: PromptBuilder[BatchNewsEventPromptInput],
        config: BatchExtractionConfig,
    ) -> None:
        self._structured_llm: StructuredOutputLLM = structured_llm
        self._parser: NewsEventParser = parser
        self._prompt_builder: PromptBuilder[BatchNewsEventPromptInput] = prompt_builder
        self._config: BatchExtractionConfig = config

    async def extract(
        self,
        articles: Tuple[Article, ...],
    ) -> LLMExtractionResult:
        inferences: List[LLMInferenceResult] = []
        errors: List[ExtractionError] = []
        successful_batches: int = 0
        for batch in self._batches(articles):
            try:
                parsed: NewsEventParseResult = await self._extract_batch(batch)
            except Exception as error:
                errors.append(
                    ExtractionError(
                        kind=self._batch_error_kind(error),
                        message=f"Batch extraction failed: {type(error).__name__}",
                        article_ids=tuple(article.id for article in batch),
                    )
                )
                continue
            inferences.extend(parsed.inferences)
            errors.extend(parsed.errors)
            successful_batches += 1
        if articles and successful_batches == 0:
            raise AllExtractionBatchesFailedError("All OpenAI extraction batches failed")
        return LLMExtractionResult(
            inferences=tuple(inferences),
            successful_batches=successful_batches,
            errors=tuple(errors),
        )

    async def _extract_batch(
        self,
        articles: Tuple[Article, ...],
    ) -> NewsEventParseResult:
        prompt_input: BatchNewsEventPromptInput = BatchNewsEventPromptInput(
            articles=articles
        )
        messages: List[ChatMessage] = self._prompt_builder.build(prompt_input)
        response: NewsEventExtractionResponse = await self._structured_llm.generate(
            messages=messages,
            response_model=NewsEventExtractionResponse,
        )
        return self._parser.parse(response, articles)

    def _batches(self, articles: Tuple[Article, ...]) -> Iterator[Tuple[Article, ...]]:
        batch_size: int = self._config.max_articles_per_batch
        for index in range(0, len(articles), batch_size):
            yield articles[index : index + batch_size]

    @staticmethod
    def _batch_error_kind(error: Exception) -> ExtractionErrorKind:
        if isinstance(
            error,
            (
                StructuredOutputResponseError,
                InferenceResultValidationError,
                ValidationError,
            ),
        ):
            return ExtractionErrorKind.RESPONSE_PROCESSING
        return ExtractionErrorKind.API_CALL
