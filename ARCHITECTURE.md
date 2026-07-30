# 전체 아키텍처

## 목적과 기준 문서

이 문서는 현재 구현의 계층, 의존성 방향, 실행 조립 방식을 설명한다. 제품의 최종 목표와 변하지 않는 원칙은 [PROJECT_GUIDE.md](PROJECT_GUIDE.md)를 기준으로 한다. 구현 세부 규칙은 [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md), LLM 경계는 [LLM_GUIDELINES.md](LLM_GUIDELINES.md)를 따른다.

## 계층 구조

```text
외부 Provider / OpenAI SDK / CLI
              ↓
Provider · Normalizer · LLM Adapter
              ↓
Article · NewsEvent · Screening · Cross Validation Domain
              ↓
Policy · Resolver · Analyzer · Aggregator · Scorer · Recommender
              ↓
LangGraph ScreeningWorkflow / Harness / CLI Bootstrap
```

`app/models/`는 외부 계층을 모르는 immutable Pydantic Domain 모델을 둔다. `NewsEvent`는 필수 상위 EventType과 선택적 독립 EventFact tuple을 보존하며, Parser가 LLM transport를 검증한다. `app/analyzers/`의 exhaustive Rule Catalog는 Fact별 direction/reason을 소유하고, Policy는 eligibility만 소유한다. `app/aggregators/`의 adapter가 eligible observation을 하나씩 기존 scoring evidence로 변환한다. `app/scorers/`의 Config/Catalog는 direction weight를 소유하고 Strategy는 contribution provenance가 포함된 final ScoringResult를 만든다. `app/core/`는 Skill request/result/error/metadata와 공통 예외 계약을 둔다. 상위 계층은 하위의 추상 인터페이스에 의존하며, Domain 모델은 OpenAI SDK, LangGraph, CLI를 import하지 않는다.

`app/recommenders/`는 `RecommendationPolicyConfig` 하나를 주입받아 score threshold를 해석한다. threshold 값의
유효성은 `RecommendationThresholdSnapshot` Domain Value가 소유하고, Policy는 `RecommendationDecision`과
result-level policy version을 생성한다. Engine은 Policy 결과를 재조립하지 않는다. CLI adapter만 내부 explainability
필드를 legacy JSON schema로 변환하므로 Domain policy와 외부 표현의 책임이 분리된다.

`app/candidates/`는 `RecommendationResult` 이후의 deterministic candidate-selection policy와 Engine을 둔다.
`RankingPolicyConfig`와 exhaustive Catalog가 action eligibility, priority, candidate limit을 소유하며 Policy는
candidate audit trail만 만든다. Workflow는 이 internal result를 보존하지만 CLI adapter는 candidate status, rank,
reason code, policy version을 출력하지 않는다. v1 action eligibility는 Catalog가 명시·검증하는 고정 제품
정책이고, priority만 교체 가능한 ranking policy 값이다.

`app/harness/`는 Phase 9의 실행 상태와 운영 side effect를 소유한다. `ScreeningExecutionHarness`는 terminal audit를 만들고 optional JSONL sink에 저장한다. audit reader는 metrics report를 만들며, alert decorator는 durable audit 저장 뒤에만 best-effort delivery를 시도한다. daily scheduler는 주입된 Harness job을 UTC 기준으로 호출하고, retention은 archive rotation 및 review-only prune plan으로 로그 보존을 관리한다. 이 계층 밖의 Workflow·Policy·LLM은 파일 I/O, scheduler, alert delivery를 알지 않는다.

## 주요 구성 요소

| 경계 | 책임 | 현재 구현 위치 |
| --- | --- | --- |
| Provider | 외부 원본을 community별 `RawPost`로 수집 | `app/providers/` |
| Normalizer | Provider 형식을 공통 `Post`/`Article`로 변환 | provider별 normalizer 구현과 `app/models/normalize.py` |
| Evaluator | 기사 처리 대상 여부를 관측 | `app/evaluators/` |
| Extractor | Article에서 `NewsEvent`를 추출 | `app/extractors/` |
| Screener | 이벤트의 점수를 평가하고 Policy에 전달 | `app/screeners/` |
| Cross Validator | 비교 기사와의 근거 관계를 평가 | `app/cross_validators/` |
| Company Directory | KRX name index에서 canonical candidate 사실을 제공 | `app/resolvers/`, `app/config/` |
| Policy | screening, 검증, resolve의 최종 상태를 결정 | 각 기능의 `policy.py` |
| 후속 처리 | ticker 해석, 영향 분석, 증거 집계, 점수, 추천 | `app/resolvers/`, `app/analyzers/`, `app/aggregators/`, `app/scorers/`, `app/recommenders/` |
| Workflow | 단계 호출과 상태 전달 | `app/workflows/` |
| Bootstrap/CLI | 의존성 조립 및 사용자 I/O | `app/bootstrap.py`, `app/cli.py` |

## LLM 경계

LLM은 Extractor, Screener, Cross Validator에서만 구조화된 관측 결과를 만든다. 응답 DTO는 transport boundary이며 Parser가 타입·범위·index·중복·도메인 규칙을 검사한 뒤 Domain 객체로 만든다. Policy가 `ACCEPT/REVIEW/REJECT`, 검증 상태, 독립 출처 수를 결정한다.

OpenAI mode에서는 하나의 `AsyncOpenAI`와 `OpenAIResponsesStructuredOutputClient`, 그리고 stateless `OpenAIResponsesStructuredOutputLLM` gateway를 Extractor·Screener·Cross Validator가 공유한다. 각 호출은 `response_model`을 인자로 전달하므로 현재 gateway는 작업별 상태를 보유하지 않는다. 이 전제가 바뀌면 client만 공유하고 작업별 gateway를 분리한다.

OpenAI 실행은 `ProviderRequestBudget`을 통해 context-local request cap을 공유한다. `ScreeningExecutionHarness`가 scope를 열고 budgeted gateway가 SDK 호출 전에 slot을 claim하므로, 한 실행이 설정된 provider request 상한을 넘기지 않는다. 이 cap은 token-price accounting이 아닌 보수적 비용 상한이다.

```text
AsyncOpenAI
    ↓
OpenAIResponsesStructuredOutputClient
    ↓
OpenAIResponsesStructuredOutputLLM
    ├── LLMNewsEventExtractor
    ├── LLMEventScreener
    └── LLMEventCrossValidator
```

Mock mode는 같은 Workflow·Policy·후속 단계를 사용하고 LLM 관측 부분만 결정적 구현으로 교체한다. 따라서 Mock은 단순한 별도 제품이 아니라 빠르고 재현 가능한 계약 검증 경로다.

Company Directory mode는 LLM execution mode와 독립적이다. `empty` mode는 version `empty`의 후보 없는 immutable directory를 사용하며, `local_csv` mode는 versioned KRX CSV를 한 번 읽어 immutable name index를 만든다. Directory는 후보만 제공하고 Company Resolution Policy가 canonical ID 기반 status를 결정한다.

## 실패와 관측성

recover 가능한 item 오류는 가능한 한 해당 item만 제외하고 sibling 결과를 보존한다. provider/response/root-validation batch 오류도 나머지 batch를 계속 처리한다. 입력이 존재하지만 유효 결과가 하나도 없을 때만 해당 단계의 명시적 예외를 발생시킨다. 프로그래밍 오류와 object identity 불변식 위반은 숨기지 않고 전파한다.

로그는 `structlog`만 사용한다. batch index, event/evidence index, 내부 식별자, 제한된 error kind 같은 운영용 메타데이터만 기록하며 기사 본문, prompt, SDK 전체 응답, API key, 개인정보, 무제한 예외 문자열을 기록하지 않는다.

## 의존성 및 변경 원칙

- Provider/SDK/LLM adapter는 Domain 모델을 만들지 않고 transport 결과만 제공한다.
- Parser는 Policy, DB, LLM 호출을 하지 않는다.
- Policy는 Prompt 구성이나 OpenAI 호출을 하지 않는다.
- Workflow는 서비스의 세부 구현을 알지 않고 주입된 인터페이스를 호출한다.
- 새 외부 통합은 adapter와 config를 추가하고, Domain/Policy 계약을 우회하지 않는다.
- 상태 생성·갱신·저장은 Harness/Workflow 경계에서만 수행한다.
