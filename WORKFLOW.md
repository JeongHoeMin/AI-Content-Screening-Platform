# Workflow 상세 계약

## 공통 계약

`ScreeningWorkflow`는 LangGraph로 실행되며 bootstrap에서 주입한 interface만 호출한다. 모든 노드는 immutable tuple 중심의 state를 입력·출력으로 사용한다. `NewsEvent` object identity는 Extract → Screen → Cross Validation → Resolve 사이의 연결 키이므로 동등하지만 다른 객체로 교체하면 안 된다.

recover 가능한 오류는 item 또는 batch 단위로 격리하고, 예상하지 못한 RuntimeError와 object identity 불변식 위반은 전파한다. 현재 Workflow에는 노드 수준의 자동 재시도 정책이 없다. OpenAI provider의 네트워크 재시도는 설정된 SDK `max_retries` 경계에서만 수행된다.

```text
Article
  → Evaluate → Extract → Screen → Cross Validate → Resolve
  → Analyze → Aggregate → Score → Recommend → WorkflowResult / CLI JSON
```

`Recommend` 노드는 하나의 `ScoringResult`를 `RecommendationPolicy`에 전달한다. Policy는 threshold snapshot,
reason code, action을 포함한 final immutable `RecommendationResult`를 만들고, Engine은 이를 정확히 한 번 호출해
같은 객체 identity로 반환한다. 이어지는 `Select Candidates` 노드는 RecommendationDecision만 소비해 internal
`CandidateSelectionResult`를 만들며 score/action을 수정하지 않는다. CLI는 workflow result 직렬화 경계에서만
Decision을 기존 recommendation JSON schema로 투영하고 candidate provenance는 외부 schema에 추가하지 않는다.
`ScreeningResult`는 internal `CandidateSelectionResult`를 필수로 보존한다. CLI JSON은 output projection이며
internal workflow snapshot을 재구성하는 round-trip DTO가 아니다.

## 노드 계약 형식

아래의 모든 실행 노드는 같은 여섯 개 계약 필드를 사용한다.

```text
Input → Output → Failure → Retry → Owner → Responsibility
```

- **Input**: 직전 노드가 보존해야 하는 Domain 값과 identity
- **Output**: 다음 노드에 전달하는 검증된 Domain 값 또는 workflow state
- **Failure**: 부분 실패를 격리하는 범위와 fatal error 조건
- **Retry**: Workflow가 소유하는 재시도 여부와 provider 재시도의 경계
- **Owner**: 결과를 관측·검증·결정하는 구현/계층
- **Responsibility**: 수행하는 일과 명시적으로 수행하지 않는 일

## 계약 요약

| Node | Input | Output | Failure 범위 | Retry | Owner |
| --- | --- | --- | --- | --- | --- |
| Evaluate | `Article[]` | `ArticleEvaluationResult[]` | 실행 오류 | 없음 | Evaluator |
| Extract | 허용된 `Article[]` | inference, `NewsEvent[]` | event, batch | SDK transport만 | LLM, Parser |
| Screen | inference | `ScreeningDecision[]` | event, batch | SDK transport만 | LLM, Parser, Policy |
| Cross Validate | REVIEW decision, article evidence | `CrossValidationResult[]` | evidence, event, batch | SDK transport만 | LLM, Parser, Policy |
| Resolve | decision, validation, company snapshot | `ResolvedNewsEvent[]` | identity 불변식 | 없음 | Company Resolver, Policy |
| Analyze | resolved event | `ImpactAnalysis[]` | 실행 오류 | 없음 | Analyzer |
| Aggregate | impact analyses | `EvidenceAggregation` | 실행 오류 | 없음 | Aggregator |
| Score | aggregation | `ScoringResult` | 실행 오류 | 없음 | Scoring strategy |
| Recommend | scoring | recommendation, statistics | 실행 오류 | 없음 | Recommendation policy |

## Evaluate

### Input

- `Article[]`

### Output

- `ArticleEvaluationResult[]`

### Failure

- 현재 규칙 evaluator의 오류는 실행 오류로 전파한다.
- 허용되지 않은 기사는 실패가 아니라 `accepted=False` 관측으로 다음 추출 대상에서 제외한다.

### Retry

- `extract`, `screen`, `cross_validate`의 OpenAI timeout, connection, authentication,
  authorization failure는 LangGraph 표준 지수 백오프로 같은 입력을 총 3회까지 재시도한다.
  최초 요청은 즉시 실행하고, 이후 재시도는 5초·10초 뒤에 실행한다.
- 3회가 모두 실패하면 workflow는 해당 stage와 safe error type을 보존하고 종료한다.
- response/parser/input-size 오류는 재시도하지 않으며 valid sibling 결과를 보존한다.

### Owner

- `ArticleEvaluator`

### Responsibility

- 기사의 처리 대상 여부를 평가한다.
- LLM 호출, event 추출, 최종 투자 판단은 수행하지 않는다.

## Extract

### Input

- `accepted=True`인 `Article[]`

### Output

- `LLMInferenceResult[]`
- 원본 identity를 유지한 `NewsEvent[]` (`event_type` 필수, `event_facts` 선택)
- 성공 batch 수

### Failure

- 빈 입력은 LLM 호출 없이 빈 결과다.
- event 단위 parser 오류는 정상 sibling event를 보존한다.
- EventType 오류는 해당 event만 제외하고, EventFact 오류는 해당 Fact만 제외해 유효 event와
  sibling Fact를 보존한다.
- provider, structured-response, root-validation 오류는 해당 batch를 건너뛰고 다음 batch를 계속 처리한다.
- 처리 대상이 있었지만 유효 inference가 0개면 단계 예외를 발생시킨다.

### Retry

- `extract`, `screen`, `cross_validate`의 OpenAI timeout, connection, authentication,
  authorization failure는 같은 입력으로 총 3회까지 LangGraph가 재시도한다.
- 3회가 모두 실패하면 workflow는 해당 stage와 safe error type을 보존하고 종료한다.
- response/parser/input-size 오류는 재시도하지 않으며 valid sibling 결과를 보존한다.
- OpenAI SDK retry는 설정이 허용하는 transport 오류에만 적용

### Owner

- `LLMNewsEventExtractor`
- extraction Parser

### Responsibility

- Article에서 구조화된 event 관측을 만든다.
- EventType은 상위 Domain Category이며 EventFact는 독립적이고 선택적인 구체 사건이다. Extractor는
  서로 다른 Category의 복합 사건을 별도 event로 분리한다.
- Parser는 transport를 Domain으로 검증한다.
- 최종 event 정책이나 투자 추천을 결정하지 않는다.

## Screen

### Input

- extraction의 `LLMInferenceResult[]`

### Output

- `ScreeningDecision[]`

### Failure

- 빈 입력은 LLM 호출 없이 빈 decision이다.
- event 단위 score/reason/index 오류는 해당 event만 제외한다.
- batch 오류는 뒤 batch 처리를 막지 않는다.
- 입력 event가 있었는데 유효 decision이 하나도 없으면 `NoValidScreeningDecisionsError`를 발생시킨다.

### Retry

- Workflow 자동 재시도 없음
- OpenAI SDK retry는 설정이 허용하는 transport 오류에만 적용

### Owner

- `LLMEventScreener` 또는 Mock Screener
- screening Parser
- `ScreeningPolicy`

### Responsibility

- LLM은 relevance, importance, credibility, 근거, cross-validation 필요성을 관측한다.
- Parser는 0–100 정수 Domain 계약을 보장한다.
- Policy만 `ACCEPT/REVIEW/REJECT`를 결정한다.

## Cross Validation

### Input

- `REVIEW` 상태의 `ScreeningDecision[]`
- 각 decision의 원본 `NewsEvent`, source `Article`, related `Article[]`

### Output

- `CrossValidationResult[]`

### Failure

- REVIEW 대상이 없으면 LLM 호출 없이 빈 결과다.
- 관련 기사가 없는 candidate는 Policy의 deterministic `INSUFFICIENT_EVIDENCE` 결과를 반환한다.
- event/evidence 단위 오류는 정상 evidence와 sibling event를 보존한다.
- batch 오류는 뒤 batch 처리를 막지 않는다.
- 대상 candidate가 있었는데 유효 result가 하나도 없으면 `NoValidCrossValidationResultsError`를 발생시킨다.

### Retry

- Workflow 자동 재시도 없음
- OpenAI SDK retry는 설정이 허용하는 transport 오류에만 적용

### Owner

- `LLMEventCrossValidator` 또는 Mock Cross Validator
- cross-validation Parser
- `CrossValidationPolicy`

### Responsibility

- LLM은 evidence별 `supports`/`conflicts`/`unrelated` 관계와 claim을 관측한다.
- Parser는 local event/evidence index, relation, claim, confidence를 검증한다.
- Policy가 independent source 연결 요소, validation status, `ValidationEvidence`를 결정한다.

## Resolve

### Input

- `ScreeningDecision[]`
- 선택적 `CrossValidationResult[]`
- event별 `TickerResolvedEvent[]` company snapshot

### Output

- `ResolvedNewsEvent[]`

### Failure

- cross-validation result가 없는 decision은 유효하며 optional validation으로 처리한다.
- 같은 event identity에 여러 validation/ticker 결과가 있거나 decision과 연결되지 않으면 불변식 오류를 전파한다.
- 모든 decision에 ticker snapshot이 없으면 불변식 오류를 전파한다.

### Retry

- Workflow 자동 재시도 없음

### Owner

- `DefaultCompanyResolver`
- `ResolvePolicy`

### Responsibility

- Company Resolution은 이 단계에서 정확히 한 번 수행하고, 결과 snapshot과 screening/validation을 같은 원본 event identity로 연결한다.
- Policy가 최종 resolve decision을 결정한다.
- 이후 단계는 Directory를 다시 조회하지 않는다. `AMBIGUOUS`·`UNRESOLVED` 회사는 snapshot에는 보존하지만 종목 evidence aggregation에서는 제외한다.
- LLM 호출이나 독립 출처 계산을 수행하지 않는다.

## Analyze

### Input

- `ResolvedNewsEvent[]`

### Output

- `ImpactAnalysis[]`

### Failure

- 현재 strategy의 예상 밖 오류는 전파한다.
- 빈 입력은 빈 analysis 결과다.

### Retry

- Workflow 자동 재시도 없음

### Owner

- `ImpactAnalyzer`
- impact strategy
- impact policy

### Responsibility

- Strategy는 등록된 Impact Rule Catalog와 `DIRECT` company relation으로 observation을 생성한다. `INDIRECT` 및 향후 Supplier/Customer/Competitor/Parent/Subsidiary relation은 별도 정책 전에는 direction을 자동 전파하지 않는다.
- Policy는 observation을 변경하지 않는 filtering만 수행하고, 허용·제외·downstream 전달 여부만 결정한다.
- 모든 observation은 `ImpactAnalysis` snapshot에 보존한다.
- `ImpactAnalysis.evaluations`는 `ImpactPolicy`가 생성하며, Strategy observation과 Policy eligibility를 하나의 immutable 값으로 결합한다. `observations`는 evaluations에서 계산되므로 별도 tuple의 길이·순서 불일치가 발생하지 않는다.
- 최종 stock score와 recommendation을 결정하지 않는다.

## Aggregate

### Input

- `ImpactAnalysis[]`

### Output

- `EvidenceAggregation`

### Failure

- 현재 strategy의 예상 밖 오류는 전파한다.
- 빈 analysis는 정의된 빈 aggregation으로 처리한다.

### Retry

- Workflow 자동 재시도 없음

### Owner

- `EvidenceAggregator`
- aggregation strategy

### Responsibility

- snapshot을 변경하거나 observation을 삭제하지 않고, policy가 eligible로 표시한 canonical `COMPANY` observation만 scoring에 사용할 downstream evidence로 선택한다. adapter는 eligible observation 하나를 `CompanyImpact` 하나로 변환하며 같은 company/event observation을 병합·상쇄·dedup하지 않는다. `UNKNOWN` 및 `AMBIGUOUS`/`UNRESOLVED` company observation은 snapshot에는 보존하고 aggregation에서만 제외한다.
- 새 기사 사실을 생성하거나 recommendation을 결정하지 않는다.

## Score

### Input

- `EvidenceAggregation`

### Output

- `ScoringResult`

### Failure

- 현재 strategy의 예상 밖 오류는 전파한다.

### Retry

- Workflow 자동 재시도 없음

### Owner

- `ScoringEngine`
- scoring strategy

### Responsibility

- 검증된 aggregation을 명시적인 규칙으로 종목 점수로 변환한다.
- Strategy는 Config와 evidence contribution으로 최종 `ScoringResult`를 만들며, Engine은 동일 객체를
  그대로 반환한다. score evidence는 `ScoreContribution`으로 보존하고 score는 contribution 합과 일치한다.
- `ScoringResult.policy_version`은 이번 scoring 실행에 사용한 policy provenance를 보관한다.
- LLM 출력만으로 점수 또는 매수 결론을 만들지 않는다.

## Recommend

### Input

- `ScoringResult`

### Output

- `RecommendationResult`
- workflow statistics

### Failure

- 현재 policy의 예상 밖 오류는 전파한다.

### Retry

- Workflow 자동 재시도 없음

### Owner

- `RecommendationEngine`
- recommendation policy

### Responsibility

- scoring 결과를 제품의 추천 관측으로 표현하고 처리 통계를 완성한다.
- 자동 주문, 초단위 거래 실행, 새로운 사실 추론을 수행하지 않는다.

## 실행 모드 및 CLI

`ExecutionMode.MOCK`은 결정적 extractor/screener/cross validator를 사용하고, `ExecutionMode.OPENAI`는 같은 structured-output gateway를 사용하는 LLM 구현을 사용한다. 이후 downstream과 CLI JSON schema는 두 mode에서 동일하다.

CLI는 `python -m app --input <articles.json> --mode mock|openai`로 실행한다. `--audit-log`는 safe terminal audit JSONL을, `--alert-log`는 audit 저장 이후 발생한 safe alert JSONL을 남긴다. `python -m app --audit-report <audit.jsonl>`는 workflow를 실행하지 않고 aggregate metrics만 출력한다. 표준 출력은 결과 또는 report JSON만 사용하고, 제한된 structlog 로그와 오류는 표준 오류로 분리한다.

## 운영 실행 계약

`ScreeningExecutionHarness`만 workflow terminal audit persistence와 provider request-budget scope를 소유한다. `DailyWorkflowScheduler`는 UTC daily schedule과 injected job lifecycle만 소유하며 실패한 job 뒤에도 다음 slot을 예약한다. `OperationalAlertPolicy`는 failed execution 및 configured duration threshold를 safe alert로 투영한다. JSONL retention은 atomic rotation과 prune candidate plan만 제공하며, 자동 파일 삭제를 수행하지 않는다.
