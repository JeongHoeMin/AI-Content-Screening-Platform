# PR30: Evidence-aware Impact Analysis v1

## Summary

PR16이 만든 현재 Impact Analyzer는 event 제목·요약의 제한된 키워드만으로 모든 회사를 같은
방향으로 처리하는 임시 결정론적 경로다. PR30은 이를 대체해, Resolve 결과와 screening 및
cross-validation 근거를 추적 가능한 영향 관측으로 변환하는 **Impact Analysis v1** 계약을
정의한다.

v1의 기본 구현은 결정론적 rule baseline이다. 이는 재현 가능한 운영 기준과 테스트 경로를 먼저
고정하기 위한 선택이며, LLM 기반 영향 관측은 같은 Domain/Parser/Policy 계약 위에 후속 PR로
추가한다. 어떤 구현도 stock score, 매수·매도 판단, recommendation을 생성하지 않는다.

## Scope

- `ResolvedNewsEvent`의 resolve decision, screening assessment, 선택적 validation 상태와
  회사 resolution snapshot을 입력으로 하는 immutable impact observation을 정의한다.
- 회사별 방향, 영향 범위, 근거 참조, 불확실성을 명시적으로 모델링한다.
- `ImpactStrategy`는 등록된 Rule Catalog로 관측만 생성하고, `ImpactPolicy`는 그 관측의
  downstream 전달 여부만 결정하도록 책임을 분리한다.
- 기본 rule strategy는 event의 명시적 company relation과 구조화된 `EventFact`만 사용하며,
  같은 입력에서 항상 같은 결과를 반환한다.
- Resolve에서 `REJECT`된 event, `AMBIGUOUS`/`UNRESOLVED` 회사, validation 근거가 부족한
  경우의 observation 보존과 aggregation 제외 규칙을 정의한다.
- 현재 `ImpactAnalysis → EvidenceAggregation → ScoringResult` 흐름의 object identity,
  company 순서, 부분 성공 계약을 보존한다.
- Domain, analyzer, policy, workflow, bootstrap/CLI 및 테스트 문서를 최종 계약에 맞춰 갱신한다.

## Non Goals

- 주가·거래량·재무제표·시장 데이터 조회 또는 가격 예측
- 매수/매도/보유 추천, stock score 또는 포트폴리오 비중 결정
- LLM이 ACCEPT/REVIEW/REJECT, 검증 상태, 독립 출처 수, 최종 투자 결론을 정하는 것
- 새 ticker/company identity 생성 또는 Company Directory 재조회
- 실시간 외부 데이터, database/cache, scheduler, 자동 매매
- LLM 기반 impact adapter, prompt, OpenAI config 변경 (후속 PR 범위)
- 기존 CLI JSON schema의 비의도적 확장

## Current State and Constraints

- `ResolvedNewsEvent`는 원본 `NewsEvent` identity, resolve decision, screening decision,
  선택적 cross-validation status와 immutable company resolution snapshot을 보관한다.
- 현 `ImpactAnalysis`는 `CompanyImpact(company, direction)`만 가지며, Rule strategy는
  제목/요약 키워드로 event-level direction 하나를 모든 회사에 복제한다. PR29a는 이 한계를
  해결하는 필수 선행 계약으로 `EventType`과 `EventFact`를 제공한다.
- `EvidenceAggregator`는 확정 ticker/company ID가 없는 company impact를 제외하고,
  이후 `ScoringResult`와 `RecommendationResult`는 이 집계값을 소비한다.
- Workflow의 Analyze 노드는 Resolve 후 한 번 실행된다. 이후 노드는 Directory를 재조회하거나
  event object를 교체하지 않는다.
- PROJECT_GUIDE와 LLM_GUIDELINES에 따라 LLM은 영향 관측만 보조할 수 있고, 최종 score와
  recommendation은 Policy가 소유한다.

## Approved Product Decisions

### 1. 분석 대상과 보수적 게이트

Impact Analysis는 `ResolvedNewsEvent`를 입력으로 받지만 모든 event를 종목 근거로 만들지 않는다.

- `ResolvedDecisionType.REJECT` event도 Strategy가 생성한 observation은 `ImpactAnalysis`
  snapshot에 보존한다. Policy가 해당 observation 전체를 downstream evidence에서 제외한다.
- `ACCEPT` event는 validation이 없어도 분석 대상이 될 수 있다. validation 부재는 별도
  uncertainty로 보존하며 임의의 검증 성공으로 바꾸지 않는다.
- `REVIEW` event는 해당 resolve decision과 cross-validation status를 있는 그대로 보존한다.
  v1 Policy는 `VERIFIED` 또는 `PARTIALLY_VERIFIED`가 아닌 REVIEW event를 종목 scoring 근거에서
  제외한다. 제외는 분석 실패가 아니라 policy observation이다.
- `AMBIGUOUS`와 `UNRESOLVED` company는 event-level/industry/market 관측에는 남을 수 있으나
  canonical stock evidence 및 aggregation에는 전달하지 않는다.

이 게이트는 LLM이나 Strategy가 아니라 Impact Policy가 결정한다. Policy의 결과는 filtering
metadata이며 Strategy가 만든 observation 자체를 변경하거나 삭제하지 않는다.

### 2. Direction, scope, uncertainty

방향은 `POSITIVE`, `NEGATIVE`, `NEUTRAL`, `UNKNOWN`을 유지한다.

- `UNKNOWN`: 입력 근거만으로 방향을 결정할 수 없음. 기본값이며 score에 기여하지 않는다.
- `NEUTRAL`: 영향이 없다는 적극적이고 설명 가능한 관측. v1 rule baseline은 생성하지 않는다.
- `POSITIVE`/`NEGATIVE`: 명시적 event fact와 회사 relation에 의해 지지되는 방향.

영향 범위는 `COMPANY`, `INDUSTRY`, `MARKET`, `MACRO`를 별도 값으로 표현한다. 하나의 event는
여러 범위 관측을 가질 수 있으나, Company evidence에는 canonical identity가 확정된
`COMPANY` 관측만 전달한다. uncertainty는 `LOW`, `MEDIUM`, `HIGH`처럼 제한 enum으로 모델링하며,
LLM confidence나 screening credibility를 대체하지 않는다.

### 3. Evidence provenance

모든 impact observation은 적어도 다음의 추적 경로를 보존한다.

```text
ResolvedNewsEvent identity
  → resolve decision / validation status
  → event title·summary·company relation의 제한된 사실 참조
  → ImpactObservation
  → ImpactPolicy decision
```

원문 기사, prompt, raw LLM response, 전체 후보 목록은 Domain error나 로그에 복사하지 않는다.
근거는 안전한 `reason_code` enum과 짧은 구조화된 reference로 표현하며, 문자열 설명은 최대 길이와
개수를 제한한다.

### 4. Impact Rule Catalog

Impact Strategy는 자유로운 판단을 하지 않는다. `Direction`은 반드시 등록된 Impact Rule
Catalog의 Rule ID, Direction, Reason Code 조합으로만 생성한다. Catalog는 PR29a가 Parser를
통과시킨 `EventFact`만 입력으로 받는다. 등록되지 않은 rule, 제목·요약·keywords의 재해석,
Strategy 내부의 추론으로 direction을 만들 수 없다.

v1의 최소 catalog는 다음과 같다. 이 목록의 확장은 별도 제품 계약 변경으로만 가능하다.

| Rule ID | Direction | Reason Code |
| --- | --- | --- |
| `FACTORY_EXPANSION` | `POSITIVE` | `FACTORY_EXPANSION_POSITIVE` |
| `MASS_LAYOFF` | `NEGATIVE` | `MASS_LAYOFF_NEGATIVE` |
| `BANKRUPTCY` | `NEGATIVE` | `BANKRUPTCY_NEGATIVE` |
| `PRODUCT_RELEASE` | `UNKNOWN` | `PRODUCT_RELEASE_DIRECTION_UNKNOWN` |
| `CEO_INTERVIEW` | `UNKNOWN` | `CEO_INTERVIEW_DIRECTION_UNKNOWN` |

`UNKNOWN` catalog entry도 감사 가능한 observation은 생성하지만 Policy가 stock evidence에서
제외한다. Catalog는 현재 `EventFact` Enum의 모든 값을 정확히 한 번씩 등록해야 한다. 중복 또는
누락 Fact는 Catalog 생성과 bootstrap에서 fail-fast하며, 유효 Fact가 런타임에 조용히 무시되는
상태는 허용하지 않는다. catalog는 구현 세부 사항이 아니라 versioned 제품 계약이다.

### 5. Company Relation Policy

현재 `CompanyRelation`은 `DIRECT`와 `INDIRECT`만 표현한다. v1 Impact Strategy는
`DIRECT`(Primary Company Relation) 회사에 대해서만 Rule Catalog direction을 생성한다.
`INDIRECT` 회사에는 direction을 자동 전파하지 않으며 `UNKNOWN` observation 또는 observation
없음으로 처리한다.

향후 Supplier, Customer, Competitor, Parent, Subsidiary 등 더 세분화된 relation이 추가되더라도,
별도의 relation propagation 정책이 승인되기 전에는 모두 자동 전파 대상이 아니다. 관계 기반
영향 전파는 후속 PR의 범위다.

### 6. Rule baseline

기본 Strategy는 pure, deterministic, side-effect free다. 이미 검증된 event metadata와
`EventFact`만 읽고, 제목·요약·keywords를 다시 해석하거나 네트워크·LLM·Directory·DB·cache를
호출하지 않는다. 기존의 모든 회사 동일 direction 복제는
제거한다.

- 등록된 Rule Catalog entry와 `DIRECT` company relation의 조합이 있을 때만 Fact별 회사 direction을
  관측한다.
- 상충 Fact는 positive/negative observation을 각각 원본 Fact 순서대로 보존하며 서로 상쇄하거나
  `UNKNOWN`으로 축약하지 않는다. direct relation이 없거나 Fact가 없으면 observation이 없다.
- pattern/rule은 Policy와 분리된 versioned Rule Catalog로 관리하며, 테스트에서 catalog version과
  결정 이유를 확인한다.
- Rule은 사건에 없는 회사, ticker, 산업 효과, 거시 효과를 추론하지 않는다.

## Proposed Domain and Interfaces

### Domain

기존 간단한 `CompanyImpact`/`ImpactAnalysis`는 하위 consumer를 한 번에 깨지 않도록 확장 또는
명시적 migration을 통해 아래 의미를 표현한다.

- `ImpactScope`: `COMPANY`, `INDUSTRY`, `MARKET`, `MACRO`
- `ImpactDirection`: 기존 네 값 유지
- `ImpactUncertainty`: 제한 enum (`LOW`, `MEDIUM`, `HIGH`)
- `ImpactReasonCode`: rule/transport가 공유하는 제한 enum
- `ImpactObservation`: `scope`, 선택적 resolved company, `event_fact`, direction, uncertainty,
  Strategy 전용 reason code를 갖는 immutable Domain 값
- `ImpactEvaluation`: 원본 `ImpactObservation`, `eligible`, Policy 전용 `exclusion_reason`을 하나로
  묶는 immutable 값. eligible이면 reason은 null이고 ineligible이면 정확히 하나의 reason이 필수다.
- `ImpactAnalysis`: 원본 `ResolvedNewsEvent` 동일 객체와 immutable evaluation tuple을 보관하는
  snapshot이다. `observations`는 evaluations에서 계산하는 read-only property이며 저장 필드를 중복하지 않는다.

회사별 observation은 원본 `ResolvedCompany` 객체를 그대로 참조하고 회사 입력 순서를 보존한다.
scope가 `COMPANY`가 아닌 observation에는 company를 넣지 않는다. `COMPANY` scope에는 반드시
입력 event에 존재하는 company만 참조할 수 있다.

### Strategy, Policy, Analyzer

```text
ResolvedNewsEvent
    ↓
ImpactStrategy (사실 기반 observation)
    ↓
ImpactPolicy (허용/제외, downstream evidence 결정)
    ↓
ImpactAnalysis
```

- `ImpactStrategy`는 observation을 만들며 resolve/score/recommendation 결정을 하지 않는다.
- `ImpactPolicy`는 resolved event와 strategy observation을 받아 observation 허용, 제외 및
  downstream evidence 전달 여부만 결정한다. Prompt와 OpenAI를 호출하지 않는다.
- `ImpactPolicy`는 filtering만 수행한다. `Direction`, `Scope`, `ReasonCode`, `Uncertainty`,
  observation의 company reference와 provenance를 수정·교체·삭제해서는 안 된다. 예를 들어
  `POSITIVE` observation을 `NEGATIVE`로 바꿀 수 없다.
- 단일 exclusion reason의 우선순위는 `EVENT_REJECTED` → `EVENT_REVIEW_NOT_VERIFIED` →
  `COMPANY_NOT_RESOLVED` → `COMPANY_IDENTITY_MISSING` → `UNSUPPORTED_SCOPE` →
  `UNKNOWN_DIRECTION`으로 고정한다.
- `DefaultImpactAnalyzer`는 주입된 Strategy와 Policy를 조립할 뿐 상태를 변경하지 않는다.
- recover 가능한 item 오류가 도입되면 공통 `SkillError`와 제한된 error kind로 관측한다.
  v1 deterministic strategy의 programming/configuration 오류는 숨기지 않고 전파한다.

## Workflow and Compatibility

- Analyze 노드는 Resolve 후 정확히 한 번 실행하고 `ResolvedNewsEvent` object identity를 보존한다.
- 빈 입력은 빈 analysis로 정상 완료한다. REJECT event의 policy exclusion도 observation을 보존한
  정상 결과다.
- Analysis는 Company Directory를 조회하지 않고 `ResolvedCompany.company_id`, resolution status,
  ticker snapshot만 사용한다.
- 모든 Strategy observation은 `ImpactAnalysis` snapshot에 보존한다. Aggregator는 snapshot을
  변경하거나 observation을 삭제하지 않는다.
- Aggregator는 policy가 eligible로 표시한 canonical `COMPANY` observation만 같은 `company_id`로
  묶어 downstream evidence를 선택한다. ambiguous/unresolved company 및 `UNKNOWN` direction은
  snapshot에는 남지만 stock evidence를 만들지 않는다.
- Aggregation adapter는 eligible observation 하나를 기존 `CompanyImpact` evidence 하나로 변환한다.
  동일 company/event의 observation을 adapter에서 병합·상쇄·dedup하거나 `UNKNOWN`으로 축약하지
  않는다. 기존 Aggregation이 company ID 기준으로 묶고 scoring/recommendation public contract는
  그대로 유지한다.
- Mock/OpenAI execution mode는 같은 rule baseline/Policy/Workflow 경로를 사용한다. PR30은
  OpenAI 호출을 추가하지 않는다.

## Implementation Plan

1. 현재 `impact_analysis`, analyzer strategy, aggregator/scorer consumer와 workflow state의 public
   계약을 inventory하고, 호환 migration 지점을 문서에 기록한다.
2. immutable Pydantic Domain models와 제한 enum을 추가하고, scope/company 상호 제약, tuple
   immutability, 원본 identity를 Parser/Domain 테스트로 고정한다.
3. `ImpactPolicy` protocol 및 deterministic 기본 policy를 추가해 resolve/validation/resolution
   status 기반의 filtering eligibility와 exclusion reason만 결정한다.
4. Company Relation Policy와 versioned Impact Rule Catalog를 따르는 strategy를 구현하고, 기존 broad keyword-only 전략을
   제거 또는 compatibility adapter로 격리한다.
5. `DefaultImpactAnalyzer`, workflow Analyze node, aggregator를 새 analysis outcome에 맞게
   연결한다. Bootstrap은 명시적으로 Strategy와 Policy를 주입한다.
6. CLI output 변경이 필요하면 versioned schema decision과 migration test를 먼저 추가한다.
   필요하지 않다면 현재 public JSON을 유지한다.
7. ARCHITECTURE, WORKFLOW, DOMAIN_MODEL, DECISION_LOG 및 ROADMAP을 실제 확정 계약에 맞춰
   구현과 같은 변경 단위로 갱신한다.

## Test Plan

### Domain and policy

- scope/company 상호 제약, enum 범위, immutable tuple, observation/analysis identity를 검증한다.
- ACCEPT, REVIEW, REJECT와 validation status 조합별 policy outcome 및 exclusion reason을 검증한다.
- resolved/ambiguous/unresolved company, canonical company ID 중복, ticker 없음의 경계를 검증한다.
- `UNKNOWN`과 `NEUTRAL`을 구분하고 unknown이 score evidence로 흘러가지 않는지 검증한다.

### Strategy and analyzer

- 모든 catalog rule, 미등록 rule, conflicting rule, direct/indirect relation, 근거 부족 event에서
  회사별 direction과 reason code를 검증한다.
- 같은 입력 반복 실행과 rule ordering 변경에도 결과/순서/identity가 결정적인지 검증한다.
- 빈 입력, 빈 company, mixed eligible/excluded events, configuration/programming error 전파를
  검증한다.
- Strategy가 LLM, network, Directory 또는 상태 변경을 호출하지 않는 경계를 fake로 검증한다.

### Workflow and downstream

- Resolve → Analyze → Aggregate의 event/company identity와 순서가 보존되는지 검증한다.
- REJECT, ambiguous, unresolved, unknown observation이 snapshot에는 보존되고 canonical stock
  aggregation에서만 제외되는지 검증한다.
- partial valid sibling이 유지되고, policy exclusion이 batch failure로 처리되지 않는지 검증한다.
- Mock/OpenAI mode가 동일한 impact baseline과 CLI JSON contract를 사용하는지 검증한다.

### Verification

```bash
uv run pytest
uv run python -m compileall app tests
git diff --check
```

## Acceptance Criteria

- 영향 분석 결과는 resolved event, company snapshot, validation 상태와 안전한 reason code로
  추적 가능하다.
- Direction은 등록된 Rule Catalog로만 생성되며, LLM이나 Rule strategy는 final score,
  recommendation, verification 또는 resolve decision을 생성하지 않는다.
- `ImpactPolicy`는 observation을 변경하지 않는 filtering만 수행한다.
- `UNKNOWN` 및 ambiguous/unresolved company observation은 snapshot에는 보존되고 aggregation에서만
  제외된다.
- ambiguous/unresolved company와 `UNKNOWN` observation은 종목 evidence를 만들지 않는다.
- `UNKNOWN`과 적극적 `NEUTRAL`은 Domain과 Policy에서 구분된다.
- 같은 입력과 rule set version은 동일한 impact result를 만든다.
- 원본 event/company identity, 부분 성공, Mock/OpenAI workflow, 기존 public CLI 계약이 유지된다.
- 로그와 오류 모델은 기사 원문, prompt, raw response, API key, 개인정보를 포함하지 않는다.

## Proposed Commit Message

```text
feat: add evidence-aware impact analysis
```

## Change Log

### 2026-07-30 — Initial approved implementation plan

- Phase 6의 다음 구현 단위를 evidence-aware Impact Analysis v1으로 정의했다.
- LLM adapter 추가를 분리하고, Policy 소유의 eligibility와 결정론적 company relation-aware
  baseline을 이번 범위로 제한했다.
- 기존 PR16의 event-level keyword direction 한계를 명시하고, provenance·uncertainty·scope와
  aggregation 호환성을 검증 가능한 계약으로 추가했다.

### 2026-07-30 — PR29a structured-fact dependency

- PR30 Strategy가 제목·요약·keywords를 재해석하지 않고 PR29a의 EventFact만 Rule Catalog 입력으로
  사용하도록 선행 의존성을 확정했다.

### 2026-07-30 — Rule, policy, and aggregation boundary hardening

- Direction 생성 기준을 versioned Impact Rule Catalog로 고정하고, 등록되지 않은 rule의 임의 생성을 금지했다.
- `DIRECT`만 direction 생성 대상이며 `INDIRECT`와 향후 세분 relation은 자동 전파하지 않는 Company Relation Policy를 추가했다.
- ImpactPolicy가 observation을 바꾸지 않는 filtering 계층임을 명시했다.
- 모든 observation은 snapshot에 보존하고, Aggregation만 downstream evidence를 선택·제외하도록 확정했다.

### 2026-07-30 — Implemented v1 contract

- Immutable exhaustive `ImpactRuleCatalog`, fact-level `ImpactObservation`, observation과 eligibility를
  묶는 `ImpactEvaluation`, deterministic `DefaultImpactPolicy`, and observation-to-evidence adapter를 구현했다.
- `reason_code`는 Strategy의 direction 근거, `exclusion_reason`은 Policy의 downstream 제외 근거로
  분리했다. evaluation의 eligible/reason 상호 제약은 Domain validator로 강제한다.

### 2026-07-30 — Evaluation pairing hardening

- 별도 observation/filter tuple을 제거하고 immutable `ImpactEvaluation`이 observation과 eligibility를
  원자적으로 보관하도록 변경했다.
- Analyzer는 Policy가 Strategy observation의 동일 객체와 순서를 보존하는지 검증하고, Aggregation은
  evaluation을 직접 순회한다. 이에 따라 zip 기반의 잘못된 filter 결합 경로를 제거했다.
