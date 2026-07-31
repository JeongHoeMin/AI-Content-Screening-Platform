from app.extractors.errors import AllExtractionBatchesFailedError
from app.llms.errors import StructuredOutputCallError
from app.models.cross_validation import BatchCrossValidationConfig
from app.screeners.errors import NoValidScreeningDecisionsError
from app.workflows.screening.graph import _retry_llm_stage


def test_workflow_retries_only_safe_transient_llm_errors() -> None:
    assert _retry_llm_stage(
        StructuredOutputCallError(provider="openai", error_type="APITimeoutError")
    )
    assert _retry_llm_stage(AllExtractionBatchesFailedError("APIConnectionError"))
    assert _retry_llm_stage(NoValidScreeningDecisionsError("AuthenticationError"))
    assert not _retry_llm_stage(
        StructuredOutputCallError(provider="openai", error_type="BadRequestError")
    )


def test_cross_validation_request_shape_is_bounded() -> None:
    config = BatchCrossValidationConfig()

    assert config.max_candidates_per_batch == 2
    assert config.max_related_articles_per_candidate == 5
