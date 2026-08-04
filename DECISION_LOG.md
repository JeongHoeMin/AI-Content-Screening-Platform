# Architecture Decision Records

## 사용 방법

이 문서는 프로젝트의 장기 설계 계약을 ADR(Architecture Decision Record) 형식으로 기록한다. 새 결정은 구현 전에 추가하고, 승인된 결론은 `Accepted`로 표시한다. 대체된 결정은 삭제하지 않고 `Superseded`와 대체 ADR을 연결한다. PR별 구현 이력과 검토 수정은 `docs/pr-*.md`에 기록한다.

## ADR 작성 규칙

- ADR 번호는 생성한 뒤 변경하거나 재사용하지 않는다.
- 승인된 ADR은 삭제하지 않는다.
- 설계가 변경되면 새 ADR을 추가하고 기존 ADR의 상태를 `Superseded`로 바꾼 뒤 대체 ADR을 연결한다.
- 하나의 ADR은 하나의 설계 결정만 다룬다.
- ADR에는 구현 목록이 아니라 설계의 context, decision, consequences를 기록한다.
- 상태는 최소한 `Proposed`, `Accepted`, `Rejected`, `Deprecated`, `Superseded` 중 하나를 사용한다.

# ADR-001

## Title

Domain과 외부 transport를 분리한다.

## Status

Accepted

## Context

외부 provider와 LLM 응답은 형식과 품질이 가변적이다. 이 값을 곧바로 Workflow와 Policy에 전달하면 SDK·prompt·모델 변경이 비즈니스 계약을 바꿀 수 있다.

## Decision

외부 응답은 transport DTO로 받고 Parser가 타입, 범위, index, enum, 중복을 검증해 immutable Pydantic Domain 모델로 변환한다. Domain 모델은 OpenAI SDK, LangGraph, CLI를 알지 않는다.

## Consequences

장점은 외부 변경 격리와 결정적 Policy 테스트다. 단점은 DTO와 Parser를 별도로 유지해야 하며 검증 코드가 늘어난다는 점이다.

# ADR-002

## Title

LLM은 최종 Decision을 수행하지 않는다.

## Status

Accepted

## Context

LLM의 비결정성, 환각, prompt 변화는 투자 판단의 재현성과 감사 가능성을 해칠 수 있다.

## Decision

LLM은 extraction, screening, 기사 relation, 영향 관측만 반환한다. `ACCEPT/REVIEW/REJECT`, 검증 상태, 독립 출처 수, stock score, recommendation은 Policy 또는 deterministic strategy가 결정한다. Prompt에는 Policy 임계값을 넣지 않는다.

## Consequences

결정은 재현 가능하고 Policy를 독립적으로 테스트할 수 있다. 반면 정책 구현과 domain conversion이 더 명시적으로 필요하다.

# ADR-003

## Title

부분 성공을 우선한다.

## Status

Accepted

## Context

외부 기사와 구조화 LLM 응답에서는 일부 item만 malformed인 경우가 일반적이다. item 하나의 실패로 batch 전체를 잃으면 시스템의 유용성이 크게 감소한다.

## Decision

Parser는 유효 assessment와 제한된 error observation을 함께 반환한다. item 오류는 sibling을 보존하고, batch provider/response 오류는 뒤 batch 처리를 막지 않는다. 대상이 있었지만 유효 결과가 0개일 때만 단계의 명시적 예외를 발생시킨다. 가짜 0점이나 fabricated evidence fallback은 만들지 않는다.

## Consequences

실제 데이터 품질 저하에 견고해진다. 대신 downstream은 입력 수와 결과 수가 다를 수 있음을 허용해야 하며 관측 로그가 중요해진다.

# ADR-004

## Title

Mock과 OpenAI는 하나의 Workflow 계약을 공유한다.

## Status

Accepted

## Context

개발·회귀 테스트에는 재현 가능한 실행 경로가 필요하고, production mode 전환이 business logic 차이를 만들면 안 된다.

## Decision

Mock과 OpenAI mode는 동일한 Workflow, downstream Policy, CLI JSON schema를 사용한다. mode는 extractor, screener, cross validator의 관측 구현만 교체한다.

## Consequences

Mock mode가 빠른 회귀 기준선이 된다. LLM 기능은 fake gateway와 OpenAI smoke test를 별도로 검증해야 한다.

# ADR-005

## Title

OpenAI structured-output gateway를 공유한다.

## Status

Accepted

## Context

Extractor, Screener, Cross Validator는 같은 OpenAI 설정과 SDK client를 사용하지만 서로 다른 response model을 가진다.

## Decision

현재 stateless `OpenAIResponsesStructuredOutputLLM`은 호출별 `response_model`을 받으므로 하나의 AsyncOpenAI client, structured client, gateway를 세 작업이 공유한다. gateway가 작업별 mutable state를 갖게 되면 shared client만 유지하고 gateway를 작업별로 분리한다.

## Consequences

연결과 설정을 중앙화하면서 DTO 계약을 독립적으로 유지한다. future gateway 변경 시 bootstrap 조립을 재검토해야 한다.

# ADR-006

## Title

candidate ID는 내부 전용으로 유지한다.

## Status

Accepted

## Context

Cross validation은 workflow 후보와 LLM batch 응답을 연결해야 하지만 내부 식별자를 외부 모델 계약에 노출할 필요는 없다.

## Decision

candidate ID는 내부 correlation, parser 오류 관측, 불변식 검사에만 사용한다. prompt와 LLM response는 batch-local event/evidence index를 사용한다.

## Consequences

workflow 내부 구현과 외부 model contract의 결합이 줄고 민감정보 노출 위험이 낮아진다. Parser는 local index를 안전하게 candidate로 복원해야 한다.

# ADR-007

## Title

독립 출처는 보수적인 연결 요소로 계산한다.

## Status

Accepted

## Context

재배포 기사나 같은 통신사의 표기를 여러 독립 근거로 세면 cross validation 신뢰도를 과대평가할 수 있다.

## Decision

정규화한 URL domain 또는 source가 같은 evidence를 하나의 관계로 연결하고, 그 연결 요소 수를 독립 출처 수로 계산한다. A-B가 source로 같고 A-C가 domain으로 같으면 A·B·C를 하나로 합친다. domain 정규화는 lowercase, port 제거, 선행 `www.` 제거까지만 한다.

## Consequences

독립성 과대계산을 보수적으로 방지한다. Public Suffix List와 subdomain 처리는 아직 하지 않으므로 해당 한계를 문서화하고 향후 별도 ADR로 검토한다.

# ADR-008

## Title

비식별 source 목록은 최소 집합과 정확 일치로 유지한다.

## Status

Accepted

## Context

일반 단어를 placeholder로 과도하게 제외하면 정상 언론사와 서비스명을 독립 출처 계산에서 잃을 수 있다.

## Decision

기본 비식별 source는 `unknown`, `unknown source`, `n/a`, `na`, `none`, `null`, `news`, `newsroom`만 사용한다. 정확히 정규화된 문자열이 일치할 때만 제외하며 부분 문자열과 prefix 비교를 금지한다.

## Consequences

`publisher`, `media`, `press`, `source` 같은 정상 값 가능성이 있는 문자열을 보존한다. 목록 확장은 실제 운영 데이터에서 placeholder 사용이 확인된 경우에만 한다.

# ADR-009

## Title

안전한 구조화 로그만 기록한다.

## Status

Accepted

## Context

LLM과 뉴스 데이터에는 기사 원문, prompt, 비밀값, 개인정보가 섞일 수 있으며 무제한 예외 문자열도 민감 내용을 포함할 수 있다.

## Decision

`structlog`에 batch/event/evidence index, 내부 correlation ID, 제한된 error kind만 기록한다. 기사 본문, prompt, raw SDK response, API key, 개인정보, 예외 전문은 로그 및 parse error 모델에 넣지 않는다.

## Consequences

운영자가 오류를 상관관계로 추적하면서 데이터 노출 위험을 줄인다. 상세 진단이 필요하면 별도의 보호된 관측 체계를 설계해야 한다.

# ADR-010

## Title

Company Resolution은 ticker보다 영구 company identity를 우선한다.

## Status

Accepted

## Context

ticker와 exchange는 시장 표현이며 ticker 변경, 상장폐지, 재상장, 시장 이동이 일어날 수 있다. ticker를 회사의 동일성으로 사용하면 장기적으로 같은 회사를 다른 entity로 보거나 다른 회사를 잘못 합칠 수 있다. 또한 회사명 alias가 여러 개여도 하나의 회사 identity를 가리킬 수 있다.

## Decision

Company Resolution v1은 KRX 상장사만 지원하고 승인된 KRX 기반 versioned local CSV를 유일한 master data로 사용한다. `CanonicalCompany.company_id`를 ticker와 독립적인 영구 identity로 정의하고, Business Logic은 ticker가 아닌 `company_id`로 동일성을 비교한다.

`CompanyDirectory`는 canonical name과 alias의 정규화·name index 조회·candidate 제공만 수행하며 후보를 선택하지 않는다. 동일 alias가 다른 company ID를 가리키는 것은 configuration error가 아니라 `AMBIGUOUS` 후보로 보존한다. `CompanyResolutionPolicy`는 distinct company ID 수가 1개이면 `RESOLVED`, 0개이면 `UNRESOLVED`, 2개 이상이면 `AMBIGUOUS`로 결정한다. 모호하거나 미해결된 경우 ticker는 만들지 않는다.

Company Resolution은 Workflow에서 정확히 한 번 수행되며 이후 단계는 immutable resolution snapshot만 소비한다. external API, 실시간 sync, 다중 시장은 별도 ADR로 확장한다.

## Consequences

같은 version의 local master data와 같은 입력은 결정적으로 같은 결과를 낸다. ticker lifecycle 변화에도 company identity의 의미를 보존할 수 있고, 모호성을 임의의 ticker 선택으로 숨기지 않는다. `AMBIGUOUS`·`UNRESOLVED`는 snapshot에는 보존하지만 종목 evidence aggregation에는 포함하지 않는다. 반면 KRX 외 시장은 지원하지 않으며 master data 갱신은 운영 절차가 책임져야 한다.

# ADR-011

## Title

Impact direction은 versioned Rule Catalog로만 생성한다.

## Status

Accepted

## Context

자유로운 keyword 또는 관계 해석으로 direction을 생성하면 구현마다 positive/negative 기준이 달라지고, 근거 없는 관계 전파가 종목 evidence에 들어갈 수 있다.

## Decision

Impact Strategy는 등록된 Impact Rule Catalog의 Rule ID, Direction, Reason Code 조합으로만 observation을 생성한다. 등록되지 않은 rule은 direction을 생성할 수 없다. v1은 `CompanyRelation.DIRECT`만 direction 생성 대상으로 하며 `INDIRECT`는 자동 전파하지 않는다. Supplier, Customer, Competitor, Parent, Subsidiary 등 향후 세분 relation도 별도 propagation 정책 없이는 자동 전파 대상이 아니다.

## Consequences

Direction 생성 기준이 제품 계약으로 고정되고 Rule 확장은 명시적 review 대상이 된다. v1은 간접 영향의 일부를 보수적으로 `UNKNOWN` 또는 observation 없음으로 남기며, 관계 전파의 정교화는 후속 결정으로 분리한다.

# ADR-012

## Title

Impact Policy는 filtering만 수행하고 observation은 snapshot에 보존한다.

## Status

Accepted

## Context

Policy가 direction이나 근거를 고치면 Strategy의 관측과 Policy의 결정을 구분할 수 없고, aggregation에서 제외된 관측을 삭제하면 감사와 후속 정책 변경이 어려워진다.

## Decision

ImpactPolicy는 observation 허용, 제외, downstream 전달 여부만 결정한다. Policy는 direction, scope, reason code, uncertainty, company reference, provenance를 수정·교체·삭제하지 않는다. 모든 observation은 `ImpactAnalysis` snapshot에 보존하며, Aggregation만 policy가 eligible로 표시한 observation을 downstream evidence로 선택한다. `UNKNOWN` 및 `AMBIGUOUS`/`UNRESOLVED` company observation은 snapshot에는 남고 aggregation에서만 제외된다.

## Consequences

Strategy는 observation 생성, Policy는 filtering, Aggregation은 evidence 선택이라는 경계가 고정된다. 모든 관측을 유지하므로 provenance와 감사 가능성이 높아지지만, downstream consumer는 snapshot 전체와 eligible evidence를 구분해야 한다.

# ADR-013

## Title

EventType과 EventFact를 분리한다.

## Status

Accepted

## Context

개별 사건을 상위 Category enum에 직접 넣으면 Domain 분류와 Fact가 섞이고, Impact Analysis가 제목·요약을 다시 해석하면 Extractor와 책임이 중복된다.

## Decision

NewsEvent은 필수 EventType과 선택적 복수 EventFact를 가진다. EventType은 안정적인 상위 Domain Category이며 EventFact는 독립적인 구체 사건이다. EventFact의 순서는 보존하고 중복은 첫 값만 남긴다. Type을 결정하지 못한 event는 recoverable parser 오류로 제외하고, Fact를 결정하지 못한 유효 event는 빈 Fact 목록으로 보존한다. PR30 Impact Rule Catalog는 EventFact만 소비한다.

## Consequences

새 사건은 가능한 한 EventFact만 추가해 확장할 수 있고, EventType의 churn을 줄인다. Fact 없는 event도 Screening·Resolve 등 공통 흐름에서 유효하지만 Fact 기반 Impact observation은 만들지 않는다.

# ADR-014

## Title

EventType과 EventFact 호환성은 교체 가능한 table로 분리한다.

## Status

Accepted

## Context

EventFact Enum 내부에 Category 호환성을 넣으면 Fact 값과 v1 정책이 결합되고, 새로운 Rule Set이나 Consumer가 다른 compatibility 정책을 사용하려면 Domain 모델을 변경해야 한다.

## Decision

EventFact와 EventType은 서로 직접 참조하지 않는 순수 Domain Enum으로 유지한다. immutable `EventTypeCompatibility` table이 호환성 행을 소유하며, Parser는 생성자 주입된 table로 Fact를 검증한다. default table은 v1 규칙을 제공하지만 다른 Consumer는 Enum 변경 없이 별도 table을 사용할 수 있다. table은 EventFact Enum의 모든 값을 정확히 하나의 EventType에 등록해야 하며, 중복 또는 누락 Fact 귀속은 table 생성 시 fail-fast한다.

## Consequences

v1 호환성은 명시적이고 테스트 가능하며, 정책 교체가 Domain 값의 의미를 바꾸지 않는다. Domain 모델을 직접 구성할 때는 compatibility를 강제하지 않으므로 외부 transport 검증은 반드시 Parser 경계를 통해 수행해야 한다.

# ADR-015

## Title

Impact observation은 exhaustive Fact Catalog와 filtering 결과를 분리한다.

## Status

Accepted

## Context

제목·요약 키워드 기반 impact는 EventFact 계약을 우회하고, Policy가 direction을 수정하거나
aggregation이 observation을 합치면 감사 가능한 원인과 downstream 선택 근거가 섞인다.

## Decision

PR30은 모든 EventFact를 정확히 한 번씩 등록하는 immutable `ImpactRuleCatalog`를 사용한다.
Strategy는 DIRECT company와 Fact마다 독립 observation을 만들고 상충 관측을 보존한다. Policy는
자신의 immutable 출력인 `ImpactEvaluation`으로 observation과 eligibility를 원자적으로 묶으며 exclusion 우선순위를 고정하고 observation을 수정하지
않는다. Aggregation adapter는 eligible evaluation의 observation 하나를 legacy CompanyImpact 하나로 변환하고
병합·상쇄·dedup하지 않는다.

## Consequences

방향 생성, downstream 선택, 기존 scoring 호환의 책임이 분리된다. 기존 scoring 계약은 유지되지만
전체 provenance는 ImpactAnalysis snapshot에 남으므로 후속 consumer migration이 가능하다.

# ADR-016

## Title

Stock Scoring은 atomic contribution과 exhaustive direction policy를 사용한다.

## Status

Accepted

## Context

단순 direction 합산은 각 score가 어떤 evidence에서 나왔는지 정형화해 보존하지 않으며, Strategy의
hard-coded mapping은 policy 교체와 완전성 검증을 어렵게 만든다.

## Decision

`ScoringPolicyConfig`는 policy version, weight range, exhaustive DirectionScoreCatalog를 소유한다.
Strategy는 모든 CompanyImpact를 하나의 ScoreContribution으로 변환하고 CompanyScore는 contribution만
저장한다. evidences는 contribution에서 계산한다. Strategy가 final ScoringResult를 생성하고
DefaultScoringEngine은 같은 객체를 반환한다. policy version은 result에 한 번만 보존한다.

## Consequences

direction score의 정책과 근거가 감사 가능해지고, recommendation은 기존 float score contract를 계속
소비한다. event fact, validation, uncertainty는 현재 scoring 입력이 아니므로 가중치에 사용하지 않는다.

# ADR-017

## Title

Recommendation은 threshold snapshot을 포함한 immutable decision을 생성한다.

## Status

Accepted

## Context

기존 recommendation은 action만 남겨 동일 score가 어떤 threshold 정책으로 판단되었는지 감사할 수 없었다.
반면 CLI JSON schema를 곧바로 확장하면 기존 소비자와의 호환이 깨진다.

## Decision

Policy는 strict ordered `RecommendationThresholdSnapshot`을 가진 Config를 주입받고 CompanyScore마다
action·reason code·snapshot을 보존하는 `RecommendationDecision`을 만든다. `RecommendationResult`는
policy version과 decision tuple을 소유하며 Engine은 Policy 반환 객체를 그대로 전달한다. CLI adapter는
Decision을 기존 score/recommendation JSON shape로 투영하고 explainability provenance는 internal Domain에 둔다.

## Consequences

추천 결과는 정책 근거를 잃지 않으면서 CLI public contract를 유지한다. reason code나 threshold를 외부에 노출하는
새 API/CLI schema는 별도 버전의 후속 작업으로 다룬다.

# ADR-018

## Title

Candidate Selection은 recommendation을 재해석하지 않는 deterministic audit trail이다.

## Status

Accepted

## Context

추천 action만으로는 여러 매수 가능한 회사 중 어떤 항목이 limit 안에 선택됐는지와 제외 근거를 설명할 수 없다.
반면 Candidate Selection이 score contribution이나 impact evidence를 다시 읽으면 PR30~32의 책임 경계가 흐려진다.

## Decision

Policy는 `RecommendationDecision`의 action과 score만 소비한다. exhaustive ranking catalog와 max-candidate
config로 eligible Decision을 priority, score, input index 순으로 결정적으로 정렬한다. Result는 input order의
evaluation audit trail을 저장하고 selected rank와 exclusion reason을 보존한다. Workflow는 internal result를
보관하지만 CLI schema는 변경하지 않는다.

v1 Catalog의 eligibility는 STRONG_BUY/BUY eligible 및 나머지 not eligible이라는 고정 제품 정책을 명시한다.
Catalog는 이 값의 교체를 허용하지 않고 fail-fast하며, priority만 ranking 순서를 위한 교체 가능한 값이다.
action별 candidate reason은 Domain helper가 단일 소유하고 Policy와 validator가 함께 사용한다.

## Consequences

후보 선택의 재현성과 감사 가능성이 생기며 scoring/recommendation 결과는 그대로 유지된다. portfolio allocation,
risk weighting, market data 및 사용자별 후보 정책은 후속 policy로 분리된다.

# ADR-019

## Title

운영 side effect는 Harness-owned safe execution records로 분리한다.

## Status

Accepted

## Context

daily execution에는 audit, metrics, alerting, retention, cost·latency·secret 관리가 필요하지만 이를 Workflow·Policy·LLM에 넣으면 판단과 side effect가 결합되고 민감 정보가 로그로 새기 쉽다.

## Decision

`ScreeningExecutionHarness`가 execution-scoped request budget 및 terminal audit를 소유한다. Scheduler는 injected Harness job만 호출하고, alerting은 persisted audit 이후의 best-effort adapter로 분리한다. JSONL retention은 archive rotation과 review-only prune plan만 제공한다. OpenAI budget은 token 가격이 아닌 execution당 provider request hard cap이며, CLI와 config repr는 raw exception/API key를 로그에 남기지 않는다.

## Consequences

운영 관측과 recoverable side effect는 안전하게 독립되지만 external notifier, scheduler deployment, distributed coordination, token accounting은 명시적 후속 통합으로 남는다.

# ADR-020

## Title

실시간 시장 입력은 실행 단위의 immutable snapshot으로 전환한다.

## Status

Accepted

## Context

뉴스·공시 API와 KRX 종목 마스터는 외부에서 변하며, resolver가 각 이름 해석마다 네트워크를 호출하면 동일 실행 안에서도 후보 집합이 달라지고 외부 장애가 분석 흐름에 전파된다.

## Decision

Naver News와 OpenDART는 source-specific `RawPost`를 반환하고 normalizer가 공통 `Post`로 변환한다. CLI의 collect boundary가 텍스트가 있는 Post만 Article로 투영한다. KRX API mode는 KOSPI·KOSDAQ·KONEX을 실행 시작 시 병렬 조회해 date-versioned `StaticCompanyDirectory` snapshot을 만든 뒤, resolver에는 그 immutable snapshot만 주입한다. 각 market의 recoverable API 실패는 다른 market snapshot을 보존하되, 유효 entry가 전혀 없으면 실행을 시작하지 않는다.

## Consequences

한 실행의 company mapping은 재현 가능하며 directory version으로 추적된다. API key와 raw response는 로그나 결과에 남지 않는다. API snapshot refresh는 다음 실행에서만 일어나며, 뉴스 전문 추출과 외부 community provider 확대는 별도 수집 단위로 유지한다.

# ADR-021

## Title

투자 테마·뉴스 주제 수집 조건은 versioned 결정적 catalog와 run-scoped snapshot으로 관리한다.

## Status

Accepted

## Context

사용자는 개별 기업명이 아닌 반도체·AI·대체에너지 같은 종목군과 뉴스 주제로 분석 범위를 좁혀야 한다. 이
판단을 LLM에 맡기면 같은 입력의 재현성·비용·감사 가능성이 낮아지고, 원문을 운영 로그에 저장하면 노출
범위가 불필요하게 커진다.

## Decision

`ThemeCatalog`는 versioned term mapping으로 Article 제목·본문을 결정적으로 관측한다. 선택한 테마와 주제가
모두 존재하면 AND로 판정하고, `ArticleFilter`가 원본 identity를 보존한 통과 목록과 안전한 제외 사유를
반환한다. Dashboard Harness는 `collection_filter_snapshots`에 run ID, 선택 enum, catalog version, 건수
집계와 UTC 시각만 저장한다.

## Consequences

수집 조건을 나중에 재현할 수 있고, filter 변경은 catalog version으로 추적된다. 정교한 의미 분류,
임베딩 기반 유사도, 개별 기업 필터, 원문을 포함한 감사 저장은 별도 범위로 유지한다.

# ADR-022

## Title

운영 분석 입력은 승인된 RSS 전문으로 제한한다.

## Status

Accepted

## Context

실제 OpenDART 전문 조회에서 목록은 수신되었지만 다수 항목이 파일 부재(`014`)로 끝났다. 전문이 없는
공시 제목·메타데이터를 LLM에 보내면 근거·문단 계약을 만족하지 못하고, Naver 검색 snippet은 분석 전문이
아니다.

## Decision

대시보드와 CLI의 기본 분석 source는 `IR_RSS_FEEDS`에 운영자가 등록한 기업·기관 공식 RSS/Atom 전문으로
한다. 피드가 없으면 명시적 configuration 오류로 중단한다. DART는 전문 파일이 존재하는 경우에만 명시적으로
선택하는 보조 진단 source로 남긴다. DART `014`, 빈 RSS 본문, parser 오류는 retry하지 않는 부분 실패이며,
RSS transport timeout·connection 오류만 재시도 후보가 된다.

## Consequences

분석 입력의 전문·근거 계약이 명확해진다. 운영자는 승인한 RSS URL을 관리해야 하며, RSS 보존 기간 밖의
과거 재현은 수집 당시 스냅샷 또는 장기 보존 피드를 필요로 한다.

# ADR-023

## Title

대시보드 워크플로우 그래프는 terminal 재시도 관측만 표시한다.

## Status

Accepted

## Context

사용자는 수집부터 후보 선택까지의 실제 처리 경로와 LLM 재시도 상태를 확인해야 한다. 하지만 현재 LangGraph
`updates` stream은 노드 완료만 제공하고 내부 retry attempt마다 안전한 별도 이벤트를 제공하지 않는다. 이를
우회해 원문, prompt 또는 SDK 예외 전문을 UI로 전달하면 보안 로깅 원칙을 위반할 수 있다.

## Decision

대시보드는 수집·directory와 실제 LangGraph 노드를 순서대로 연결한 그래프를 렌더링한다. `extract`,
`deduplicate`, `screen`, `cross_validate`에는 기존의 총 3회 재시도 정책(최초 실행 뒤 5초·10초)을 보조 경로로
표시한다. 실행 중에는 재시도 가능 정책만 표시하고, retry exhaustion으로 terminal failure가 된 경우에만
`WorkflowStageRetriesExhaustedError`의 bounded stage, error type, attempts를 실패 경로에 표시한다.
그 외 terminal error는 allowlist된 error type 또는 `unexpected_error`로 정규화하고 attempts를 1회로 제한한다.

## Consequences

사용자는 실제 노드 순서, 현재 단계, 완료 상태와 재시도 소진 결과를 확인할 수 있다. 중간 retry attempt의
실시간 관측은 LangGraph 경계에서 안전한 callback 계약을 별도로 설계한 후에만 추가한다. 허용 기사가 없는
정상 조건 분기처럼 실행하지 않은 노드는 완료가 아닌 `미실행`으로 표시한다. 이 분기는 Workflow가 evaluator
결과로 계산한 bounded `next_node`를 사용하므로 대시보드가 수집 필터 결과로 실제 graph edge를 추정하지 않는다.

# ADR-024

## Title

정기 추천은 KST cron과 PostgreSQL lease로 실행하고 Telegram은 terminal observer로 분리한다.

## Status

Accepted

## Decision

작업 시간은 사용자 입력·화면에서 `Asia/Seoul`로 해석하되 DB에는 UTC를 저장한다. `schedule-worker`가 due slot을 DB transaction으로 claim해 다음 slot과 execution status를 기록한다. Telegram은 성공한 recommendation terminal 상태 뒤에만 best-effort로 동작한다. 설정 변경은 32자 이상의 environment-only password를 확인하고 HttpOnly session cookie를 발급한 브라우저에만 허용한다.

## Consequences

worker 재시작과 dashboard 재시작은 shell cron 상태에 의존하지 않는다. 원문, prompt, Telegram secret과 설정 비밀번호는 정기 설정·실행 테이블과 logs에서 제외한다. HTTPS 운영에서는 secure cookie를 유지하고, 로컬 HTTP 검증 때만 명시적으로 secure cookie를 끈다.
