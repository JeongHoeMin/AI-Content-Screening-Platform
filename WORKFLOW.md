# Workflow 상세

## 현재 실행 흐름

`ScreeningWorkflow`는 LangGraph로 구성되며, bootstrap이 주입한 서비스만 호출한다. 기사 평가 결과에 따라 추출 단계를 실행할지 분기하고, 이후 단계는 다음 순서로 진행한다.

```text
입력 Article
  → Evaluate
  → Extract
  → Screen
  → Cross Validate (REVIEW만)
  → Resolve
  → Analyze
  → Aggregate
  → Score
  → Recommend
  → WorkflowResult / CLI JSON
```

## 노드별 계약

| 단계 | 입력 | 출력 | 결정 주체 |
| --- | --- | --- | --- |
| Evaluate | `Article` | `ArticleEvaluationResult` | evaluator 규칙 |
| Extract | 허용된 `Article` | `LLMInferenceResult`, `NewsEvent` | Parser가 유효 event 확정 |
| Screen | 추출 inference | `ScreeningDecision` | `ScreeningPolicy` |
| Cross Validate | `REVIEW` decision | `CrossValidationResult` | `CrossValidationPolicy` |
| Resolve | decision + 선택적 validation + ticker | `ResolvedNewsEvent` | `ResolvePolicy` |
| Analyze | resolved event | `ImpactAnalysis` | 분석 전략 |
| Aggregate | impact analyses | `EvidenceAggregation` | 집계 전략 |
| Score | evidence | `ScoringResult` | scoring 전략 |
| Recommend | scoring | `RecommendationResult` | recommendation policy |

현재 cross validation은 `REVIEW` decision만 후보로 만든다. 후보는 원본 event object identity로 추적되며, 동일 event를 가진 `ScreeningDecision`과 결과가 정확히 연결되어야 한다. 검증 결과가 일부 누락되어도 Resolve는 남아 있는 decision으로 계속 진행하며, 없는 validation은 선택적 입력으로 취급한다.

## 상태와 identity

Workflow state는 각 노드의 결과를 immutable tuple 중심으로 전달한다. `NewsEvent`의 object identity는 extract → screen → cross validation → resolve 경계에서 연결 키로 사용한다. 따라서 복사된 동등 객체로 원본 event를 대체해서는 안 되며, 여러 결과가 하나의 event identity를 가리키는 것은 불변식 오류다.

후속 단계에는 `ScreeningDecision`만 전달된다. screening 단계에서 유효하지 않았던 candidate에 가짜 0점 decision을 만들지 않는다. 이 계약은 item 수준 부분 성공을 안전하게 유지한다.

## 실행 모드

### Mock

`ExecutionMode.MOCK`은 deterministic extractor, screener, cross validator를 사용한다. 나머지 Workflow와 downstream Policy는 OpenAI mode와 동일하다. 로컬 개발, 회귀 테스트, CLI schema 검증의 기본 모드다.

### OpenAI

`ExecutionMode.OPENAI`는 OpenAI structured output LLM 기반 Extractor, Screener, Cross Validator를 조립한다. Cross validation 뒤의 resolver, analyzer, aggregator, scorer, recommender는 현재 결정적 구현을 유지한다. OpenAI 설정은 `app/config/openai.py`의 환경변수 계약을 사용한다.

## 실패 처리

- 빈 입력은 성공한 빈 결과이며 불필요한 LLM 호출을 하지 않는다.
- 개별 event/evidence의 파싱 오류는 해당 결과만 제외하고 제한된 경고 로그로 관측한다.
- provider·structured response·root response 오류는 해당 batch를 건너뛰고 뒤 batch를 계속 처리한다.
- 처리 대상이 있었으나 유효 결과가 0개이면 해당 LLM 단계의 명시적 예외로 실행을 실패시킨다.
- 예상하지 못한 RuntimeError와 identity 위반은 전파한다.

## CLI 계약

`python -m app screening --input <articles.json> --mode mock|openai`가 표준 입력 경로다. 표준 출력은 workflow 결과 JSON만 사용하고, 운영 로그와 오류는 표준 오류로 분리한다. mode에 관계없이 최종 JSON schema는 유지되어야 한다.

## 향후 확장 기준

Company mapping, richer impact analysis, portfolio optimization을 추가할 때에도 event→decision→resolved event의 identity 계약과 Policy 최종 결정 원칙은 유지한다. 새 노드는 상태 필드를 명시하고, 이전 단계의 외부 계약을 임의로 변경하지 않는다.
