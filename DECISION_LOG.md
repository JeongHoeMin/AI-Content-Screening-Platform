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
