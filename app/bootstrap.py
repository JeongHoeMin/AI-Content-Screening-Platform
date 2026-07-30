from __future__ import annotations

from collections.abc import Callable
from enum import Enum

from openai import AsyncOpenAI

from app.aggregators import DefaultAggregationStrategy, DefaultEvidenceAggregator
from app.analyzers import (
    DEFAULT_IMPACT_RULE_CATALOG,
    DefaultImpactAnalyzer,
    DefaultImpactPolicy,
    RuleImpactStrategy,
)
from app.cross_validators import CrossValidationPolicyConfig, DefaultCrossValidationAssessmentParser, DefaultCrossValidationPolicy, LLMEventCrossValidator
from app.config import (
    CompanyDirectoryConfig,
    OpenAIConfig,
    create_company_directory,
    load_company_directory_config,
    load_openai_config,
)
from app.extractors import DefaultNewsEventParser, LLMNewsEventExtractor
from app.llms import (
    OpenAIResponsesStructuredOutputClient,
    OpenAIResponsesStructuredOutputLLM,
    StructuredOutputClient,
    StructuredOutputLLM,
    create_async_openai_client,
)
from app.models import (
    DEFAULT_SCORING_POLICY_CONFIG,
    BatchCrossValidationConfig,
    BatchExtractionConfig,
    BatchScreeningConfig,
)
from app.evaluators import RuleArticleEvaluator, RuleArticleEvaluatorConfig
from app.mock_screening import (
    DeterministicMockCrossValidator,
    DeterministicMockExtractor,
    DeterministicMockScreener,
)
from app.recommenders import DefaultRecommendationEngine, RuleRecommendationPolicy
from app.prompts import CrossValidationPromptBuilder, NewsEventPromptBuilder, ScreeningPromptBuilder
from app.resolvers import CompanyResolutionPolicy, DefaultCompanyResolver, DefaultResolvePolicy
from app.scorers import DefaultScoringEngine, EvidenceAwareScoringStrategy
from app.screeners import (
    DefaultScreeningAssessmentParser,
    DefaultScreeningPolicy,
    LLMEventScreener,
)
from app.workflows import ScreeningWorkflow


class ExecutionMode(str, Enum):
    MOCK = "mock"
    OPENAI = "openai"


WorkflowFactory = Callable[[], ScreeningWorkflow]


def create_screening_workflow(
    mode: ExecutionMode = ExecutionMode.MOCK,
) -> ScreeningWorkflow:
    factory: WorkflowFactory | None = _WORKFLOW_FACTORIES.get(mode)
    if factory is None:
        mode_name: str = mode.value if isinstance(mode, ExecutionMode) else repr(mode)
        raise ValueError(f"Unsupported execution mode: {mode_name}")
    return factory()


def _create_mock_workflow() -> ScreeningWorkflow:
    screening_policy: DefaultScreeningPolicy = DefaultScreeningPolicy()
    cross_validation_policy: DefaultCrossValidationPolicy = (
        DefaultCrossValidationPolicy(CrossValidationPolicyConfig(use_url_domain_identity=False))
    )
    directory_config: CompanyDirectoryConfig = load_company_directory_config()
    return ScreeningWorkflow(
        evaluator=RuleArticleEvaluator(RuleArticleEvaluatorConfig()),
        extractor=DeterministicMockExtractor(),
        screener=DeterministicMockScreener(screening_policy),
        cross_validator=DeterministicMockCrossValidator(cross_validation_policy),
        resolver=DefaultCompanyResolver(
            create_company_directory(directory_config),
            CompanyResolutionPolicy(),
        ),
        resolve_policy=DefaultResolvePolicy(),
        impact_analyzer=DefaultImpactAnalyzer(
            RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG),
            DefaultImpactPolicy(),
        ),
        evidence_aggregator=DefaultEvidenceAggregator(DefaultAggregationStrategy()),
        scoring_engine=DefaultScoringEngine(
            EvidenceAwareScoringStrategy(DEFAULT_SCORING_POLICY_CONFIG)
        ),
        recommendation_engine=DefaultRecommendationEngine(RuleRecommendationPolicy()),
    )


def _create_openai_workflow() -> ScreeningWorkflow:
    """Assemble the OpenAI extractor with deterministic downstream stages."""
    config: OpenAIConfig = load_openai_config()
    directory_config: CompanyDirectoryConfig = load_company_directory_config()
    sdk_client: AsyncOpenAI = create_async_openai_client(
        api_key=config.api_key,
        timeout_seconds=config.timeout_seconds,
        max_retries=config.max_retries,
    )
    structured_client: StructuredOutputClient = OpenAIResponsesStructuredOutputClient(
        sdk_client
    )
    structured_llm: StructuredOutputLLM = OpenAIResponsesStructuredOutputLLM(
        client=structured_client,
        model=config.model,
    )
    screening_policy: DefaultScreeningPolicy = DefaultScreeningPolicy()
    cross_validation_policy: DefaultCrossValidationPolicy = (
        DefaultCrossValidationPolicy()
    )
    return ScreeningWorkflow(
        evaluator=RuleArticleEvaluator(RuleArticleEvaluatorConfig()),
        extractor=LLMNewsEventExtractor(
            structured_llm=structured_llm,
            parser=DefaultNewsEventParser(),
            prompt_builder=NewsEventPromptBuilder(),
            config=BatchExtractionConfig(),
        ),
        screener=LLMEventScreener(
            structured_llm=structured_llm,
            parser=DefaultScreeningAssessmentParser(),
            prompt_builder=ScreeningPromptBuilder(),
            policy=screening_policy,
            config=BatchScreeningConfig(),
        ),
        cross_validator=LLMEventCrossValidator(structured_llm=structured_llm, parser=DefaultCrossValidationAssessmentParser(), prompt_builder=CrossValidationPromptBuilder(), policy=cross_validation_policy, config=BatchCrossValidationConfig()),
        resolver=DefaultCompanyResolver(
            create_company_directory(directory_config),
            CompanyResolutionPolicy(),
        ),
        resolve_policy=DefaultResolvePolicy(),
        impact_analyzer=DefaultImpactAnalyzer(
            RuleImpactStrategy(DEFAULT_IMPACT_RULE_CATALOG),
            DefaultImpactPolicy(),
        ),
        evidence_aggregator=DefaultEvidenceAggregator(DefaultAggregationStrategy()),
        scoring_engine=DefaultScoringEngine(
            EvidenceAwareScoringStrategy(DEFAULT_SCORING_POLICY_CONFIG)
        ),
        recommendation_engine=DefaultRecommendationEngine(RuleRecommendationPolicy()),
    )


_WORKFLOW_FACTORIES: dict[ExecutionMode, WorkflowFactory] = {
    ExecutionMode.MOCK: _create_mock_workflow,
    ExecutionMode.OPENAI: _create_openai_workflow,
}
