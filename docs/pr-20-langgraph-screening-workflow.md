# PR #20 LangGraph AI Screening Workflow MVP

## Summary

- ScreeningWorkflow는 Article을 RecommendationResult와 실행 관측값이 담긴
  ScreeningResult로 변환하는 유일한 public entrypoint다.
- LangGraph, State, Node, compiled graph는 Workflow 내부 구현이며 호출자는 직접
  참조하지 않는다.
- RuleArticleEvaluator는 LLM 분석 대상의 최소 입력 검증만 하고, LLM은 batch event
  inference에만 사용한다.

## Workflow Overview

```text
Article
  ↓
RuleArticleEvaluator
  ↓ accepted?
  ├─ no  → Aggregate → Score → Recommend
  └─ yes → LLMNewsEventExtractor → Resolve → Impact → Aggregate → Score → Recommend
```

- 모든 Node는 입력 State를 변경하지 않고 자신이 생산한 필드만 포함한 Mapping을 반환한다.
- 빈 입력과 all-rejected 입력은 LLM을 호출하지 않으며, empty Domain input을 거쳐
  RecommendationEngine이 생성한 RecommendationResult(companies=())로 정상 종료한다.
- Domain 또는 LLM 예외는 retry, wrapping, recovery 없이 그대로 전파한다.

## Layer Responsibilities

- ScreeningWorkflow는 orchestration만 담당하고 내부 LangGraph를 캡슐화한다.
- RuleArticleEvaluator는 title/content의 whitespace-normalized 최소 유효성만 검증한다.
  기본 min_body_length는 200이고 config로 교체할 수 있다. language, 광고, relevance,
  Article score, 투자 중요도 판단은 수행하지 않는다.
- StructuredOutputLLM은 준비된 messages와 Pydantic response schema로 typed structured
  output을 생성한다. Prompt 작성, batch 분할, retry, event validation, response mapping은
  담당하지 않는다.
- LLMNewsEventExtractor는 batch 분할·병합과 PromptBuilder/StructuredOutputLLM/Parser
  orchestration을 담당한다. max_articles_per_request=20은 batch 크기 정책이며 실행 방식
  (현재 순차, 향후 병렬)은 implementation detail이다.
- Parser는 ID, duplicate, cardinality를 검증하고 입력 Article 순서로 inference를
  재정렬한다.
- 기존 Resolver, Analyzer, Aggregator, Scorer, Recommender는 기존 비즈니스 책임만
  수행한다.

## LLM Output Layer

- LLMInferenceResult는 article-level immutable snapshot이며 article, events, summary,
  reasoning, confidence를 보관한다. Workflow 종료까지 변경 없이 유지되어 Human Review,
  Prompt Evaluation, Observability, Explanation의 입력으로 재사용될 수 있다.
- confidence는 0.0 이상 1.0 이하의 LLM self-reported confidence다. Domain 정답 확률이
  아니며 Workflow와 Domain의 의사결정에 사용하지 않는다.
- reasoning은 internal chain of thought가 아니라 사용자가 읽을 수 있는 1–2문장 rationale다.
  Prompt는 내부 추론을 요청하거나 저장하지 않는다.
- NewsEvent는 순수 사건 Domain이다. LLM metadata를 추가하지 않으며 inference.events의
  동일 NewsEvent 객체는 Resolver와 이후 Workflow에서 보존된다.

## Execution Results

- WorkflowStatistics는 Domain Model이 아닌 observability용 execution metadata다. total,
  accepted, rejected articles와 extracted events를 기록한다.
- ScreeningResult는 RecommendationResult와 WorkflowStatistics를 분리해 반환한다.
  RecommendationEngine은 statistics를 알지 못하고 RecommendationResult만 생성한다.
- WorkflowContext는 현재 비어 있는 immutable 확장 지점이며, 향후 model, run ID, trace,
  timeout metadata를 담을 수 있다.

## Future Roadmap

- token budget, concurrent batch execution, retry, reflection, human approval
- prompt optimization and evaluation, confidence review, explanation, ranking, portfolio
- persistence, API, scheduler, UI, multi-agent and multi-source screening
