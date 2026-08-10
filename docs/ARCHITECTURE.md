# 전체 아키텍처

## 목적과 기준 문서

이 문서는 현재 구현의 계층, 의존성 방향, 실행 조립 방식을 설명한다. 제품의 최종 목표와 변하지 않는 원칙은 [PROJECT_GUIDE.md](PROJECT_GUIDE.md)를 기준으로 한다. 구현 세부 규칙은 [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md), LLM 경계는 [LLM_GUIDELINES.md](LLM_GUIDELINES.md)를 따른다.

## 계층 구조

```text
외부 Provider / OpenAI SDK / CLI
              ↓
Provider · Normalizer · LLM Adapter
              ↓
Article · Collection Filter · NewsEvent · Screening · Cross Validation Domain
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

`app/harness/`는 Phase 9의 실행 상태와 운영 side effect를 소유한다. `ScreeningExecutionHarness`는 terminal audit를 만들고 optional JSONL sink와 PostgreSQL persistence adapter에 저장한다. audit reader는 metrics report를 만들며, alert decorator는 durable audit 저장 뒤에만 best-effort delivery를 시도한다. daily scheduler는 주입된 Harness job을 UTC 기준으로 호출하고, retention은 archive rotation 및 review-only prune plan으로 로그 보존을 관리한다. 이 계층 밖의 Workflow·Policy·LLM은 파일 I/O, scheduler, alert delivery를 알지 않는다.

추천 가격도 Harness 경계를 따른다. `RecommendationPriceRecorder`와 `RecommendationPerformanceService`만 추천 결과를
가격 관측·PostgreSQL persistence와 연결한다. `MarketPriceService`는 KIS 실시간 현재가를 먼저 관측하고,
KIS가 미설정이거나 제한된 오류 관측을 반환하면 KRX 최근 거래일 종가를 fallback으로 관측한다. KIS/KRX adapter와
Parser는 외부 응답을 검증된 관측으로만 만들고, Workflow·Policy·LLM은 가격 API나 가격 저장소를 호출하지 않는다.
entry snapshot은 변경하지 않으며 latest snapshot은 별도 identity로 저장한다. 한 종목의 가격 확인 실패는
`UNAVAILABLE` 관측으로 남고 다른 추천이나 원래 recommendation 실행을 실패시키지 않는다. 과거에
`UNAVAILABLE`로 저장된 entry만 `RecommendationEntryPriceBackfill`이 원래 추천 시각을 기준으로
`KrxClosingPriceClient`의 일 종가로 회복한다. 재조회가 가격을 찾지 못하거나 전송 예외가 나면 entry는
계속 `UNAVAILABLE`로 두되, 해당 시도의 제한된 `error_kind`를 저장해 대시보드의 재조회 버튼 옆 사유를
최신 상태로 갱신한다. 이미 확인된 entry는 절대 덮어쓰지 않고, daily worker는 KST 날짜마다 한 번만 이
best-effort 백필을 실행한다.

`GET /api/runs/history`는 저장된 entry/latest 스냅샷만 투영하므로 외부 가격 API를 호출하지 않는다.
브라우저는 그 응답을 즉시 렌더하고 `POST /api/runs/history/{run_id}/refresh`로 회차별 latest 관측을
독립 갱신한다. `POST /api/runs/history/{run_id}/items/{recommendation_index}/entry-price`는 미확인 entry
한 건만 회복한다. 이 API는 모두 Dashboard consumer 경계이며 Workflow·Policy·LLM은 가격 조회·저장과
browser 갱신을 알지 않는다.

`app/filters/`의 `ArticleFilter`와 versioned `ThemeCatalog`는 정규화된 Article의 제목·본문만 읽어 투자 테마와 뉴스 주제 일치 여부를 결정한다. 대시보드 Harness는 통과 Article만 Workflow로 넘기며, `CollectionFilterPersistence`를 통해 실행 ID·선택 enum·카탈로그 버전·건수 집계만 PostgreSQL에 저장한다. Provider·Normalizer·Parser·Policy·Workflow는 이 저장소를 직접 호출하지 않는다.

`app/web/`의 대시보드는 `DashboardRunManager`가 Harness 실행을 SSE로 안전하게 투영한 consumer다. 브라우저의
워크플로우 그래프는 실행을 제어하거나 재시도를 직접 수행하지 않으며, 수집·directory 상태와 `WorkflowProgressEvent`
완료 노드, terminal 실패의 bounded stage/error type/attempt count만 표시한다. 따라서 기사 원문, prompt, raw SDK
응답과 예외 전문은 UI 상태에도 포함되지 않는다. 조건 분기로 실행하지 않은 노드는 브라우저가 후속 실제 node
event와 Workflow가 제공하는 bounded `next_node`를 기준으로 `미실행`으로 투영하며, 단순 완료 순번이나 수집
필터 결과로 실행 여부를 추측하지 않는다.

SSE는 best-effort 진행 상태 transport이며 terminal 결과의 기준은 `GET /api/runs/{run_id}`다. 브라우저가 SSE
오류를 관측하면 제한된 횟수로 stream을 다시 연결하고 결과 endpoint가 `409`를 반환하는 동안 실행 중 상태를
유지한다. 완료 결과를 받으면 결과 endpoint로 화면을 복구하고, 실제 server terminal failure 또는 복구 예산 소진
때만 중단 상태를 표시한다. dashboard는 stream open·terminal 전송·close와 browser 연결 오류를 실행 ID, 제한된
lifecycle/attempt 값만 가진 structlog event로 기록하며 원문·prompt·SDK 응답·자격 증명·예외 전문은 기록하지
않는다. 실행 상태는 dashboard process 메모리에 있으므로 컨테이너 재시작 뒤의 진행 중 실행은 복구 대상이 아니다.

## 주요 구성 요소

| 경계 | 책임 | 현재 구현 위치 |
| --- | --- | --- |
| Provider | 외부 원본을 community별 `RawPost`로 수집 | `app/providers/` |
| Normalizer | Provider 형식을 공통 `Post`/`Article`로 변환 | provider별 normalizer 구현과 `app/models/normalize.py` |
| Collection Filter | 선택한 투자 테마·뉴스 주제를 결정적으로 판정 | `app/filters/`, `app/models/collection_filter*.py` |
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

LLM은 Extractor, Deduplication Comparator, Screener, Cross Validator에서만 구조화된 관측 결과를 만든다. 응답 DTO는 transport boundary이며 Parser가 타입·범위·index·중복·도메인 규칙을 검사한 뒤 Domain 객체로 만든다. Deduplication Policy는 confidence 80 이상인 `same` 관측만 병합하며, Policy가 `ACCEPT/REVIEW/REJECT`, 검증 상태, 독립 출처 수를 결정한다.

OpenAI mode에서는 하나의 `AsyncOpenAI`와 `OpenAIResponsesStructuredOutputClient`, 그리고 stateless `OpenAIResponsesStructuredOutputLLM` gateway를 Extractor·Screener·Cross Validator가 공유한다. 각 호출은 `response_model`을 인자로 전달하므로 현재 gateway는 작업별 상태를 보유하지 않는다. 이 전제가 바뀌면 client만 공유하고 작업별 gateway를 분리한다.

OpenAI 실행은 `ProviderRequestBudget`을 통해 context-local request cap을 공유한다. `ScreeningExecutionHarness`가 scope를 열고 budgeted gateway가 SDK 호출 전에 slot을 claim하므로, 한 실행이 설정된 provider request 상한을 넘기지 않는다. 이 cap은 token-price accounting이 아닌 보수적 비용 상한이다. LangGraph는 timeout, connection, authentication, authorization 오류에 한해 동일 LLM stage를 총 3회 시도한다.

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

Company Directory mode는 LLM execution mode와 독립적이다. `empty` mode는 version `empty`의 후보 없는 immutable directory를 사용하며, `local_csv` mode는 versioned KRX CSV를 한 번 읽어 immutable name index를 만든다. `krx_api` mode는 실행 시작 시 KOSPI·KOSDAQ·KONEX KRX OpenAPI를 병렬 조회해 하나의 날짜 기반 immutable snapshot을 만든다. 이후 Directory는 네트워크를 호출하지 않고 후보만 제공하며 Company Resolution Policy가 canonical ID 기반 status를 결정한다.

## 실패와 관측성

recover 가능한 item 오류는 가능한 한 해당 item만 제외하고 sibling 결과를 보존한다. provider/response/root-validation batch 오류도 나머지 batch를 계속 처리한다. 입력이 존재하지만 유효 결과가 하나도 없을 때만 해당 단계의 명시적 예외를 발생시킨다. 프로그래밍 오류와 object identity 불변식 위반은 숨기지 않고 전파한다.

로그는 `structlog`만 사용한다. batch index, event/evidence index, 내부 식별자, 제한된 error kind 같은 운영용 메타데이터만 기록하며 기사 본문, prompt, SDK 전체 응답, API key, 개인정보, 무제한 예외 문자열을 기록하지 않는다.
Docker dashboard 실행은 `./runtime/logs` volume에 구조화 application JSONL과 terminal execution audit JSONL을 보존한다. 이 runtime data는 Git에 포함하지 않는다.

정기 추천은 별도 `schedule-worker` process가 PostgreSQL의 KST cron 설정을 lease로 claim한 뒤 기존 RSS recommendation Harness를 호출한다. 설정·lease·terminal execution status는 `ScheduledRecommendationPersistence`만 변경한다. Telegram adapter는 terminal audit 뒤의 best-effort observer이며 전송 실패가 recommendation 결과를 바꾸지 않는다. 대시보드에서 직접 시작한 실행도 terminal 결과와 저장된 entry snapshot을 바탕으로 같은 안전한 요약을 전송하지만, scheduled 실행은 worker observer만 전송해 중복을 막는다.

대시보드와 Telegram의 운영 시각은 `Asia/Seoul`(KST)로 투영하고, persistence의 관측 시각과 거래일 기준은
검증 가능한 UTC/거래일 값으로 보존한다. 성과 표시는 Harness가 계산한 사후 단순 가격 비교이며 수수료·세금·배당,
실제 체결 가격이나 투자 판단을 포함하지 않는다.

## Skill / Agent / Harness 경계

### Skill

- 하나의 Skill은 하나의 명확한 작업만 수행한다.
- Skill은 상태를 직접 변경하지 않는다.
- Skill은 다른 Skill의 내부 구현에 의존하지 않는다.
- Skill 입력과 출력은 가능하면 Pydantic 모델로 표현한다.
- 모든 Skill은 공통 인터페이스 `async execute(request) -> result`를 따른다.
- Skill은 Harness, LangGraph, CLI, API 같은 실행 환경을 알지 않는다.
- Skill은 자신의 책임 범위 안에서 필요한 Service를 사용할 수 있지만, 직접 생성하지 않고 외부에서 의존성으로 주입받는다.
- Recover 가능한 실패는 Exception 제어 흐름으로 표현하지 않고 Result의 error 관측값으로 반환한다.
- Recover 불가능한 실패만 Exception으로 처리한다.
- Skill은 "판단"이 아니라 자신의 책임 범위에서 관측한 사실을 반환한다.

### Agent

- Agent는 의사결정과 오케스트레이션만 담당한다.
- Agent는 외부 API, 데이터베이스, 파일 시스템, 상태 저장소를 직접 변경하지 않는다.
- Agent는 필요한 작업을 Skill 호출로만 수행한다.
- Agent가 사용하는 프롬프트는 반드시 `app/prompts/`의 PromptBuilder를 통해 생성한다.

### Harness

- Harness는 실행 흐름, 상태 변경, 입출력 연결을 담당한다.
- 상태 생성, 갱신, 저장, 복구는 Harness에서만 수행한다.
- Harness는 Agent와 Skill의 실행 결과를 검증 가능한 방식으로 기록한다.
- Harness는 Skill Result의 metadata와 errors를 기반으로 retry, ignore, fallback 같은 제어 결정을 내린다.

## Core Contract

- 프로젝트 전체 Skill 계약은 `app/core/`에 둔다.
- `SkillRequest`는 모든 Skill request 모델의 공통 base로 사용한다.
- `SkillResult`는 `data`, `metadata`, `errors`를 포함한다.
- `SkillMetadata`는 `started_at`, `finished_at`, `duration_seconds` 같은 공통 실행 관측값을 포함한다.
- Skill별 metadata는 `SkillMetadata`를 상속하거나 generic metadata 타입으로 확장한다.
- `SkillError`는 recover 가능한 실패를 표현하는 공통 관측 모델로 사용한다.
- Skill Result는 비즈니스 데이터와 실행 메타데이터를 분리한다.

## Community Collection Architecture

- 게시글 수집은 `Provider -> RawPost -> Normalizer -> NormalizeResult -> Post` 흐름을 따른다.
- Provider는 원본 데이터 수집만 담당한다.
- Provider는 공통 `Post`를 직접 만들지 않고 community별 `RawPost` 모델을 반환한다.
- `RawPost`는 단순 `payload` dict가 아니라 community별 Pydantic 도메인 모델로 정의한다.
- Normalizer는 community별 `RawPost`를 공통 `Post`로 변환한다.
- Normalizer는 `Post`를 직접 반환하지 않고 `NormalizeResult`를 반환한다.
- `NormalizeResult`는 `post` 또는 recover 가능한 `error`를 담는다.
- CollectPostsSkill은 Provider와 Normalizer 선택 로직을 직접 가지지 않고 Registry 조회만 사용한다.
- v1에서는 Resolver를 만들지 않는다. 하나의 `CommunityType`에 여러 Provider 후보가 필요해질 때 v2에서 도입한다.
- `ProviderRegistry`는 `CommunityType -> CommunityProvider` 매핑을 관리한다.
- `NormalizerRegistry`는 `CommunityType -> CommunityNormalizer` 매핑을 관리한다.
- 신규 Community 추가는 Provider, Normalizer, Registry 등록만으로 가능해야 하며 Skill 내부 조건문을 수정하지 않는다.

### CollectPostsSkill Rules

- CollectPostsSkill은 게시글 수집과 정규화된 관측 결과 반환만 담당한다.
- CollectPostsSkill은 AI 판단, LLM 호출, Prompt 사용, DB 저장, Cache 저장, 정렬 정책, 중복 제거, 광고 판별을 하지 않는다.
- CollectPostsSkill은 Provider를 병렬 실행한다.
- Provider 하나가 실패해도 다른 Provider 실행은 계속한다.
- Provider 실패, Normalizer 실패, Timeout 등 recover 가능한 실패는 Result errors에 기록한다.
- 전체 Provider가 실패한 경우에만 Exception을 발생시킨다.
- `sources`는 문자열이 아니라 `CommunityType` enum을 사용한다.
- `period`는 문자열이 아니라 `timedelta` 또는 datetime 기반 모델을 사용한다.

## 의존성 및 변경 원칙

- Provider/SDK/LLM adapter는 Domain 모델을 만들지 않고 transport 결과만 제공한다.
- Parser는 Policy, DB, LLM 호출을 하지 않는다.
- Policy는 Prompt 구성이나 OpenAI 호출을 하지 않는다.
- Workflow는 서비스의 세부 구현을 알지 않고 주입된 인터페이스를 호출한다.
- 새 외부 통합은 adapter와 config를 추가하고, Domain/Policy 계약을 우회하지 않는다.
- 상태 생성·갱신·저장은 Harness/Workflow 경계에서만 수행한다.
