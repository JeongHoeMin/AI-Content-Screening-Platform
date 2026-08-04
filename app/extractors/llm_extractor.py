from __future__ import annotations

from typing import Iterator, List, Optional, Tuple

import structlog
from pydantic import ValidationError

from app.extractors.base import NewsEventExtractor
from app.extractors.errors import AllExtractionBatchesFailedError
from app.extractors.errors import InferenceResultValidationError
from app.llms.errors import (
    StructuredOutputCallError,
    StructuredOutputResponseError,
)
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

logger = structlog.get_logger(__name__)


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
        batches: Tuple[Tuple[Article, ...], ...] = tuple(self._batches(articles))
        recovery_requests_used: int = 0
        for batch_index, batch in enumerate(batches, start=1):
            parsed, batch_errors, recovery_requests_used = await self._extract_with_recovery(
                batch=batch,
                batch_index=batch_index,
                total_batches=len(batches),
                recovery_requests_used=recovery_requests_used,
            )
            if parsed is None:
                errors.extend(batch_errors)
                continue
            inferences.extend(parsed.inferences)
            errors.extend(parsed.errors)
            successful_batches += 1
        if articles and successful_batches == 0:
            api_errors: list[ExtractionError] = [
                error for error in errors if error.kind is ExtractionErrorKind.API_CALL
            ]
            error_type: str = self._provider_error_type(api_errors[-1]) if api_errors else "ResponseProcessingError"
            raise AllExtractionBatchesFailedError(error_type)
        return LLMExtractionResult(
            inferences=tuple(inferences),
            successful_batches=successful_batches,
            errors=tuple(errors),
        )

    @staticmethod
    def _provider_error_type(error: ExtractionError) -> str:
        """Extract a bounded provider error type from the safe error observation."""
        return error.message.rsplit(": ", maxsplit=1)[-1]

    async def _extract_with_recovery(
        self,
        *,
        batch: Tuple[Article, ...],
        batch_index: int,
        total_batches: int,
        recovery_requests_used: int,
    ) -> tuple[Optional[NewsEventParseResult], Tuple[ExtractionError, ...], int]:
        """Recover one logical batch without allowing it to consume unbounded calls."""
        parsed, error = await self._attempt_batch(
            batch=batch,
            batch_index=batch_index,
            total_batches=total_batches,
            attempt=1,
            phase="initial",
        )
        if parsed is not None:
            return parsed, (), recovery_requests_used
        if error is None:
            raise RuntimeError("Failed extraction attempt must return an error observation")

        latest_error: ExtractionError = error
        for retry_attempt in range(1, self._config.max_batch_retry_attempts + 1):
            if recovery_requests_used >= self._config.max_recovery_requests:
                break
            recovery_requests_used += 1
            parsed, retry_error = await self._attempt_batch(
                batch=batch,
                batch_index=batch_index,
                total_batches=total_batches,
                attempt=retry_attempt + 1,
                phase="retry",
            )
            if parsed is not None:
                logger.info(
                    "extraction_batch_recovered",
                    batch_index=batch_index,
                    total_batches=total_batches,
                    article_count=len(batch),
                    recovery_strategy="retry",
                    recovery_requests_used=recovery_requests_used,
                    max_recovery_requests=self._config.max_recovery_requests,
                )
                return parsed, (), recovery_requests_used
            if retry_error is None:
                raise RuntimeError("Failed retry must return an error observation")
            latest_error = retry_error

        recovery_batches: Tuple[Tuple[Article, ...], ...] = tuple(
            self._batches(batch, self._config.recovery_max_articles_per_batch)
        )
        required_requests: int = len(recovery_batches)
        remaining_requests: int = self._config.max_recovery_requests - recovery_requests_used
        if len(batch) <= self._config.recovery_max_articles_per_batch or required_requests > remaining_requests:
            logger.warning(
                "extraction_batch_recovery_exhausted",
                batch_index=batch_index,
                total_batches=total_batches,
                article_count=len(batch),
                error_kind=latest_error.kind.value,
                recovery_requests_used=recovery_requests_used,
                max_recovery_requests=self._config.max_recovery_requests,
                recovery_batch_size=self._config.recovery_max_articles_per_batch,
            )
            return None, (latest_error,), recovery_requests_used

        logger.info(
            "extraction_batch_split_recovery_started",
            batch_index=batch_index,
            total_batches=total_batches,
            article_count=len(batch),
            recovery_batch_size=self._config.recovery_max_articles_per_batch,
            recovery_batch_count=required_requests,
            recovery_requests_remaining=remaining_requests,
        )
        recovered_inferences: List[LLMInferenceResult] = []
        recovered_errors: List[ExtractionError] = []
        for recovery_batch_index, recovery_batch in enumerate(recovery_batches, start=1):
            recovery_requests_used += 1
            parsed, recovery_error = await self._attempt_batch(
                batch=recovery_batch,
                batch_index=batch_index,
                total_batches=total_batches,
                attempt=recovery_batch_index,
                phase="split_recovery",
            )
            if parsed is None:
                if recovery_error is None:
                    raise RuntimeError("Failed split recovery must return an error observation")
                recovered_errors.append(recovery_error)
                continue
            recovered_inferences.extend(parsed.inferences)
            recovered_errors.extend(parsed.errors)
        if recovered_errors:
            logger.warning(
                "extraction_batch_split_recovery_partial",
                batch_index=batch_index,
                total_batches=total_batches,
                article_count=len(batch),
                recovered_article_count=len(recovered_inferences),
                failed_recovery_batch_count=sum(
                    error.kind
                    in {
                        ExtractionErrorKind.API_CALL,
                        ExtractionErrorKind.RESPONSE_PROCESSING,
                    }
                    for error in recovered_errors
                ),
            )
        if not recovered_inferences:
            return None, tuple(recovered_errors), recovery_requests_used
        return (
            NewsEventParseResult(
                inferences=tuple(recovered_inferences),
                errors=tuple(recovered_errors),
            ),
            (),
            recovery_requests_used,
        )

    async def _attempt_batch(
        self,
        *,
        batch: Tuple[Article, ...],
        batch_index: int,
        total_batches: int,
        attempt: int,
        phase: str,
    ) -> tuple[Optional[NewsEventParseResult], Optional[ExtractionError]]:
        """Execute one bounded provider attempt and log only safe correlation data."""
        logger.info(
            "extraction_batch_attempt_started",
            batch_index=batch_index,
            total_batches=total_batches,
            article_count=len(batch),
            attempt=attempt,
            phase=phase,
            max_articles_per_batch=self._config.max_articles_per_batch,
            recovery_batch_size=self._config.recovery_max_articles_per_batch,
            max_batch_retry_attempts=self._config.max_batch_retry_attempts,
            max_recovery_requests=self._config.max_recovery_requests,
        )
        try:
            parsed: NewsEventParseResult = await self._extract_batch(batch)
        except StructuredOutputCallError as error:
            extraction_error: ExtractionError = self._build_batch_error(
                batch,
                ExtractionErrorKind.API_CALL,
                f"{error.provider} request failed: {error.error_type}",
            )
        except (
            StructuredOutputResponseError,
            InferenceResultValidationError,
            ValidationError,
        ) as error:
            extraction_error = self._build_batch_error(
                batch,
                ExtractionErrorKind.RESPONSE_PROCESSING,
                self._response_error_message(error),
            )
        else:
            logger.info(
                "extraction_batch_attempt_succeeded",
                batch_index=batch_index,
                total_batches=total_batches,
                article_count=len(batch),
                attempt=attempt,
                phase=phase,
                inference_count=len(parsed.inferences),
                parser_error_count=len(parsed.errors),
            )
            for parser_error in parsed.errors:
                logger.warning(
                    "extraction_item_excluded",
                    batch_index=batch_index,
                    article_ids=parser_error.article_ids,
                    event_index=parser_error.event_index,
                    fact_index=parser_error.fact_index,
                    error_kind=parser_error.kind.value,
                )
            return parsed, None
        logger.warning(
            "extraction_batch_attempt_failed",
            batch_index=batch_index,
            total_batches=total_batches,
            article_count=len(batch),
            attempt=attempt,
            phase=phase,
            error_kind=extraction_error.kind.value,
            error_message=extraction_error.message,
            article_ids=extraction_error.article_ids,
        )
        return None, extraction_error

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

    def _batches(
        self,
        articles: Tuple[Article, ...],
        batch_size: Optional[int] = None,
    ) -> Iterator[Tuple[Article, ...]]:
        if batch_size is None:
            batch_size = self._config.max_articles_per_batch
        for index in range(0, len(articles), batch_size):
            yield articles[index : index + batch_size]

    @staticmethod
    def _build_batch_error(
        batch: Tuple[Article, ...],
        kind: ExtractionErrorKind,
        message: str,
    ) -> ExtractionError:
        return ExtractionError(
            kind=kind,
            message=message,
            article_ids=tuple(article.id for article in batch),
        )

    @staticmethod
    def _response_error_message(error: Exception) -> str:
        if isinstance(error, StructuredOutputResponseError):
            return f"Structured output response failed: {error.reason}"
        return f"Structured output response processing failed: {type(error).__name__}"
