from __future__ import annotations

from collections.abc import Callable
from typing import Optional
from enum import Enum

from openai import AsyncOpenAI

from app.aggregators import DefaultAggregationStrategy, DefaultEvidenceAggregator
from app.deduplicators import (
    DeterministicEventComparator,
    EventDeduplicator,
    LLMEventComparator,
)
from app.candidates import DefaultCandidateSelectionEngine, RuleCandidateSelectionPolicy
from app.analyzers import (
    DEFAULT_IMPACT_RULE_CATALOG,
    DefaultImpactAnalyzer,
    DefaultImpactPolicy,
    RuleImpactStrategy,
)
from app.cross_validators import CrossValidationPolicyConfig, DefaultCrossValidationAssessmentParser, DefaultCrossValidationPolicy, LLMEventCrossValidator
from app.config import (
    CompanyDirectoryConfig,
    create_company_directory_async,
    OpenAIConfig,
    create_company_directory,
    load_company_directory_config,
    load_openai_config,
)
from app.resolvers.directory import CompanyDirectory
from app.extractors import (
    DartAugmentingNewsEventExtractor,
    DartFilingEventAugmenter,
    DefaultNewsEventParser,
    LLMNewsEventExtractor,
)
from app.llms import (
    OpenAIResponsesStructuredOutputClient,
    OpenAIResponsesStructuredOutputLLM,
    StructuredOutputClient,
    StructuredOutputLLM,
    create_async_openai_client,
)
from app.llms.budget import BudgetedStructuredOutputLLM, ProviderRequestBudget
from app.models import (
    DEFAULT_RANKING_POLICY_CONFIG,
    DEFAULT_RECOMMENDATION_POLICY_CONFIG,
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
from app.prompts import (
    CrossValidationPromptBuilder,
    DeduplicationComparisonPromptBuilder,
    NewsEventPromptBuilder,
    ScreeningPromptBuilder,
)
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


WorkflowFactory = Callable[[Optional[CompanyDirectory], RuleArticleEvaluatorConfig], ScreeningWorkflow]


def create_screening_workflow(
    mode: ExecutionMode = ExecutionMode.MOCK,
    company_directory: Optional[CompanyDirectory] = None,
    evaluator_config: Optional[RuleArticleEvaluatorConfig] = None,
) -> ScreeningWorkflow:
    factory: WorkflowFactory | None = _WORKFLOW_FACTORIES.get(mode)
    if factory is None:
        mode_name: str = mode.value if isinstance(mode, ExecutionMode) else repr(mode)
        raise ValueError(f"Unsupported execution mode: {mode_name}")
    return factory(company_directory, evaluator_config or RuleArticleEvaluatorConfig())


async def create_screening_workflow_async(
    mode: ExecutionMode = ExecutionMode.MOCK,
    evaluator_config: Optional[RuleArticleEvaluatorConfig] = None,
) -> ScreeningWorkflow:
    """Create a workflow after loading any configured remote directory snapshot."""
    directory_config: CompanyDirectoryConfig = load_company_directory_config()
    company_directory: CompanyDirectory = await create_company_directory_async(directory_config)
    return create_screening_workflow(mode, company_directory, evaluator_config)


def _create_mock_workflow(
    company_directory: Optional[CompanyDirectory] = None,
    evaluator_config: RuleArticleEvaluatorConfig = RuleArticleEvaluatorConfig(),
) -> ScreeningWorkflow:
    screening_policy: DefaultScreeningPolicy = DefaultScreeningPolicy()
    cross_validation_policy: DefaultCrossValidationPolicy = (
        DefaultCrossValidationPolicy(CrossValidationPolicyConfig(use_url_domain_identity=False))
    )
    directory_config: CompanyDirectoryConfig = load_company_directory_config()
    return ScreeningWorkflow(
        evaluator=RuleArticleEvaluator(evaluator_config),
        extractor=DeterministicMockExtractor(),
        screener=DeterministicMockScreener(screening_policy),
        cross_validator=DeterministicMockCrossValidator(cross_validation_policy),
        resolver=DefaultCompanyResolver(
            company_directory or create_company_directory(directory_config),
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
        recommendation_engine=DefaultRecommendationEngine(
            RuleRecommendationPolicy(DEFAULT_RECOMMENDATION_POLICY_CONFIG)
        ),
        candidate_selection_engine=DefaultCandidateSelectionEngine(
            RuleCandidateSelectionPolicy(DEFAULT_RANKING_POLICY_CONFIG)
        ),
        event_deduplicator=EventDeduplicator(DeterministicEventComparator()),
    )


def _create_openai_workflow(
    company_directory: Optional[CompanyDirectory] = None,
    evaluator_config: RuleArticleEvaluatorConfig = RuleArticleEvaluatorConfig(),
) -> ScreeningWorkflow:
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
    request_budget: ProviderRequestBudget = ProviderRequestBudget(
        config.max_requests_per_execution
    )
    structured_llm: StructuredOutputLLM = BudgetedStructuredOutputLLM(OpenAIResponsesStructuredOutputLLM(
        client=structured_client,
        model=config.model,
    ), request_budget)
    screening_policy: DefaultScreeningPolicy = DefaultScreeningPolicy()
    cross_validation_policy: DefaultCrossValidationPolicy = (
        DefaultCrossValidationPolicy()
    )
    return ScreeningWorkflow(
        evaluator=RuleArticleEvaluator(evaluator_config),
        extractor=DartAugmentingNewsEventExtractor(
            extractor=LLMNewsEventExtractor(
                structured_llm=structured_llm,
                parser=DefaultNewsEventParser(),
                prompt_builder=NewsEventPromptBuilder(),
                config=BatchExtractionConfig(),
            ),
            augmenter=DartFilingEventAugmenter(),
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
            company_directory or create_company_directory(directory_config),
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
        recommendation_engine=DefaultRecommendationEngine(
            RuleRecommendationPolicy(DEFAULT_RECOMMENDATION_POLICY_CONFIG)
        ),
        candidate_selection_engine=DefaultCandidateSelectionEngine(
            RuleCandidateSelectionPolicy(DEFAULT_RANKING_POLICY_CONFIG)
        ),
        event_deduplicator=EventDeduplicator(
            LLMEventComparator(
                structured_llm=structured_llm,
                prompt_builder=DeduplicationComparisonPromptBuilder(),
            )
        ),
        request_budget=request_budget,
    )


_WORKFLOW_FACTORIES: dict[ExecutionMode, WorkflowFactory] = {
    ExecutionMode.MOCK: _create_mock_workflow,
    ExecutionMode.OPENAI: _create_openai_workflow,
}
