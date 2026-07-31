from app.extractors.errors import AllExtractionBatchesFailedError
from app.llms.errors import StructuredOutputCallError
from app.models.cross_validation import BatchCrossValidationConfig
from app.screeners.errors import NoValidScreeningDecisionsError
from app.workflows.screening.graph import _LLM_RETRY_POLICY, _retry_llm_stage


def test_workflow_retries_only_safe_transient_llm_errors() -> None:
    assert _retry_llm_stage(
        StructuredOutputCallError(provider="openai", error_type="APITimeoutError")
    )


def test_workflow_network_retry_uses_five_second_exponential_backoff() -> None:
    assert _LLM_RETRY_POLICY.initial_interval == 5.0
    assert _LLM_RETRY_POLICY.backoff_factor == 2.0
    assert _LLM_RETRY_POLICY.max_interval == 20.0
    assert _LLM_RETRY_POLICY.max_attempts == 3
    assert not _LLM_RETRY_POLICY.jitter
    assert _retry_llm_stage(AllExtractionBatchesFailedError("APIConnectionError"))
    assert _retry_llm_stage(NoValidScreeningDecisionsError("AuthenticationError"))
    assert not _retry_llm_stage(
        StructuredOutputCallError(provider="openai", error_type="BadRequestError")
    )


def test_cross_validation_request_shape_is_bounded() -> None:
    config = BatchCrossValidationConfig()

    assert config.max_candidates_per_batch == 2
    assert config.max_related_articles_per_candidate == 5
