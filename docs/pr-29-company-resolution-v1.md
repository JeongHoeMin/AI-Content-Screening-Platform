# PR29: Company Resolution v1

## Summary

현재 ticker resolution은 단일 이름 조회만 표현한다. PR29는 검증된 `NewsEvent`의 회사명을 KRX 상장사의 canonical company identity로 보수적으로 해석하는 Company Resolution 경계를 만든다.

이 PR의 목표는 종목을 추천하거나 가격을 예측하는 것이 아니다. 하나의 회사명에 대해 **확정**, **모호**, **미해결**을 구분하고, 확정된 경우에만 ticker를 `ResolvedNewsEvent`까지 전달하는 것이다. 모호하거나 미해결인 값에는 가짜 ticker를 만들지 않는다.

## Scope

- 기존 ticker lookup을 Company Directory 기반 resolution 계약으로 교체한다.
- KRX 상장회사 master data를 versioned local CSV로 읽는 production directory adapter를 추가한다.
- fixture 기반 in-memory/static directory는 Mock mode와 테스트를 위해 유지한다.
- 회사명 정규화, alias, ticker/exchange, canonical name, directory version/provenance를 분리한다.
- resolution 결과를 `RESOLVED`, `AMBIGUOUS`, `UNRESOLVED`로 표현하고, 최종 snapshot에는 확정 ticker만 반영한다.
- `DefaultCompanyResolver`는 directory 조회 결과를 immutable resolution snapshot으로 조립하며 투자 판단을 하지 않는다.
- 기존 Resolve 이후 workflow는 ticker가 없는 회사도 안전하게 처리하는 계약을 유지한다.

## Non Goals

- 가격 예측, 기술적 분석, 자동 매매, 포트폴리오 비중 결정
- LLM을 사용한 회사명 추측 또는 ticker 선택
- fuzzy matching만으로 모호한 회사를 자동 확정하는 정책
- 여러 시장을 한 번에 지원하는 글로벌 entity resolution
- 회사 master data의 실시간 동기화, database/cache, scheduler
- Impact Analysis, Stock Scoring, Recommendation 규칙 변경
- 기존 CLI JSON schema의 비의도적 변경

## Approved Product Decision

### Supported market

v1은 **KRX 상장사만** 지원한다. NYSE, NASDAQ 등 다른 시장과 cross-market identity는 후속 phase 및 별도 ADR의 범위다.

### Master data and versioning

Company Resolution은 승인된 KRX 기반 versioned local CSV만 신뢰한다. 실행 시 로컬 파일을 읽으며 외부 API나 실시간 조회를 수행하지 않는다.

- master data version 형식: `YYYY-MM-DD`
- 예시 version: `2026-07-29`
- 같은 입력과 같은 master data version은 항상 같은 결과를 반환해야 한다.
- 갱신은 운영 절차로만 수행한다. 자동 다운로드, scheduler, cache, database, 실시간 sync는 PR29 범위 밖이다.

v1 CSV는 `company_id`, `canonical_name`, `ticker`, `exchange`, `aliases`, `directory_version`을 제공한다. ticker는 leading zero를 보존하는 6자리 문자열이고, exchange는 `KOSPI`, `KOSDAQ`, `KONEX` 중 하나다. `aliases`는 비어 있지 않은 문자열만 담는 JSON 배열이며, 입력 검증은 누락·중복·잘못된 값을 fail-fast configuration error로 처리한다.

## Current State and Constraints

- `NewsEvent.companies`는 원본 회사명과 `CompanyRelation`을 가진다.
- 현재 ticker lookup은 이름 하나에 ticker 하나만 표현한다.
- `DefaultCompanyResolver`는 모든 event company를 순서대로 조회하고 `TickerResolvedEvent`를 만든다.
- Resolve node는 event object identity와 ticker snapshot의 일대일 연결을 검증한다.
- downstream은 `ResolvedCompany.ticker is None`을 허용한다.
- Mock/OpenAI mode는 같은 Workflow와 Resolve 계약을 사용해야 한다.

## Design Principles

1. **Identity before ticker**: ticker는 회사 identity의 한 시장 표현일 뿐이며 resolution의 유일한 의미가 아니다.
2. **Conservative resolution**: 하나 이상의 서로 다른 canonical company 후보가 남으면 `AMBIGUOUS`다. 임의로 첫 후보를 택하지 않는다.
3. **No fabricated data**: directory에 없는 회사, 비상장사, 모호한 별칭은 ticker를 만들지 않는다.
4. **Deterministic and explainable**: 같은 directory version과 같은 입력은 같은 결과를 내고, 결과는 어떤 이름 규칙으로 나왔는지 제한된 provenance를 가진다.
5. **Directory is data access; Policy is decision**: directory adapter는 후보 사실을 제공하고 resolver policy가 확정/모호/미해결을 결정한다. Prompt나 LLM은 이 경계에 없다.
6. **No sensitive logging**: company query 원문이나 외부 전체 payload를 로그에 남기지 않는다. 제한된 resolution status, directory version, candidate count만 관측한다.

## Proposed Domain and Contract

### Canonical company identity

`CanonicalCompany`는 최소한 다음의 immutable 정보를 표현한다.

- company ID
- canonical company name
- market identifier
- ticker
- exchange
- source directory version 또는 effective date

`ResolvedTicker`의 현재 ticker/exchange 필드는 하위 호환을 위해 유지한다. canonical name과 market identity를 외부 CLI 결과에 바로 추가할지는 별도 output-versioning 결정 없이는 하지 않는다.

### Canonical Company Identity

`company_id`는 Directory 내부에서 Canonical Company를 식별하는 영구 식별자다.

- ticker 변경과 무관하게 동일하다.
- exchange 변경과 무관하게 동일하다.
- 회사 identity를 표현하며 시장 표현인 ticker는 별도 속성으로 관리한다.
- Business Logic은 회사 동일성 비교에 ticker가 아닌 `company_id`를 사용한다.

이 계약은 상장폐지, 재상장, ticker 변경 같은 후속 lifecycle 변화가 있어도 회사 identity를 다시 설계하지 않게 한다.

### Resolution observation

resolver 내부 계약은 다음 상태를 명시한다.

```text
RESOLVED
  정확히 하나의 canonical company 후보가 정책상 확정됨

AMBIGUOUS
  둘 이상의 서로 다른 canonical company 후보가 남음

UNRESOLVED
  유효 후보가 없음
```

각 observation은 상태와 관계없이 directory version을 가진다. local CSV version은 `YYYY-MM-DD`, empty directory version은 `empty`다. `candidate_count`는 raw row/alias match 수가 아니라 company ID 기준으로 중복 제거된 canonical candidate 수다. 후보의 전체 목록이나 외부 raw payload는 workflow state·로그·CLI JSON에 넣지 않는다.

### Candidate set 결정 규칙

Directory가 canonical name 또는 alias index로 찾은 후보는 `company_id` 기준으로 먼저 중복 제거한다. 여러 alias가 하나의 canonical identity를 가리키는 것은 모호성이 아니다.

```text
Company query
    ↓
CompanyDirectory candidate set
    ↓  (company_id 기준 중복 제거)
Canonical identity count
    ├── 0 → UNRESOLVED → ticker 없음
    ├── 1 → RESOLVED   → 해당 canonical ticker 사용
    └── 2 이상 → AMBIGUOUS → ticker 없음
```

### Directory interface

`CompanyDirectory`는 이름을 정규화하고 alias index를 조회해 canonical candidate를 반환하는 사실 제공 interface다. 입력 문자열을 수정하지 않고, network/DB/cache 구현은 adapter 안에 숨긴다. v1의 production adapter는 승인된 KRX versioned local CSV를 읽는다.

Directory의 책임은 다음으로 한정한다.

- canonical name과 alias의 정규화 및 동일 name index 등록
- name index 조회
- canonical candidate와 directory version 제공

Directory는 다음을 수행하지 않는다.

- 후보 선택 또는 resolution status 결정
- 투자 판단
- fuzzy ranking 또는 LLM 기반 의미 추론
- 존재하지 않는 ticker 생성

directory는 후보를 제공할 뿐 최종 선택을 하지 않는다. `CompanyResolutionPolicy`는 다음을 적용한다.

- 정확한 canonical name 또는 등록된 alias가 하나의 canonical identity만 가리키면 `RESOLVED`
- 서로 다른 canonical identity가 두 개 이상이면 `AMBIGUOUS`
- 후보가 없으면 `UNRESOLVED`

정규화는 최소한 trim, 연속 공백 축소, case normalization으로 시작한다. Unicode/NFKC, 음역, fuzzy matching, 법인 접미사 제거는 운영 데이터와 별도 ADR 없이는 추가하지 않는다.

### Workflow compatibility

`TickerResolvedEvent`는 원본 `NewsEvent` identity와 회사 순서를 보존한다. `ResolvedCompany`는 확정된 경우에만 `ResolvedTicker`를 가진다. `AMBIGUOUS`와 `UNRESOLVED`는 ticker가 없는 정상 resolution 결과다.

Company Resolution은 Workflow에서 정확히 한 번만 수행한다. Resolve 이후의 Analysis, Aggregate, Score, Recommendation은 Directory를 다시 조회하지 않고 `TickerResolvedEvent` 및 `ResolvedNewsEvent` snapshot만 소비한다. v1에서 상태가 user-facing CLI contract에 필요한지 여부는 의도적인 output-versioning 없이 확대하지 않는다.

```text
NewsEvent
    ↓
CompanyDirectory
    ↓
Candidate CanonicalCompany set
    ↓
CompanyResolutionPolicy
    ├── RESOLVED
    ├── AMBIGUOUS
    └── UNRESOLVED
    ↓
ResolvedCompany
    ↓
TickerResolvedEvent
```

## Implementation Changes

### Models

- canonical company identity와 resolution status/observation을 표현하는 immutable Domain 모델을 추가한다.
- 현 `ResolvedTicker`, `ResolvedCompany`, `TickerResolvedEvent`의 기존 필드와 event identity 계약을 유지한다.
- public JSON/CLI output에 새 필드를 노출하는 경우에는 명시적인 schema compatibility 검토와 테스트를 먼저 추가한다.

### Directory and Policy

- 후보 조회를 위한 `CompanyDirectory` protocol과 versioned local master-data adapter를 추가한다.
- `StaticCompanyDirectory`는 empty mode와 unit test의 deterministic directory로 사용한다.
- `CompanyResolutionPolicy`는 후보를 `RESOLVED`/`AMBIGUOUS`/`UNRESOLVED`로 결정한다.
- 같은 company ID master row의 중복, 누락 company ID/ticker/exchange, 잘못된 alias JSON, 잘못된 version metadata를 fail-fast configuration error로 처리한다. 서로 다른 회사의 alias collision은 유효한 ambiguous index로 보존한다.

### Resolver

- `DefaultCompanyResolver`가 event별·company별 observation을 조립한다.
- 각각의 `NewsEvent`는 한 개의 `TickerResolvedEvent`를 반환하고, company 순서와 원본 relation을 보존한다.
- directory의 recover 가능한 개별 query 실패가 모델링 가능한지 먼저 계약으로 결정한다. v1 local directory에서는 구성 오류를 fatal로 전파하고, 미등록은 정상 `UNRESOLVED`로 처리한다.
- resolver는 LLM 호출, 투자 판단, event 변경, fallback ticker 생성을 하지 않는다.

### Bootstrap

- Directory mode는 Mock/OpenAI execution mode와 독립적이다. `empty` mode가 기본이며 `local_csv` mode에서는 검증된 CSV path가 필수다.
- OpenAI client, prompt, extractor/screener/cross-validator 조립은 변경하지 않는다.
- local master data의 경로·version은 Pydantic config로 검증하고, 비밀값이 아닌 운영 설정으로 관리한다.

### Documentation and ADR

- `DECISION_LOG.md`의 ADR-010이 Company Resolution의 보수적 확정 규칙을 기록한다.
- `DOMAIN_MODEL.md`, `ARCHITECTURE.md`, `WORKFLOW.md`, `DEVELOPMENT_GUIDE.md`는 최종 계약이 확정된 경우에만 함께 갱신한다.
- actual master data의 시장 범위, 출처, version/effective-date는 문서화한다.

## Test Plan

### Domain and master data

- canonical company identity와 resolution observation의 immutability 및 필수 필드를 검증한다.
- canonical name/alias 정규화, exact alias match, 공백·대소문자 처리를 검증한다.
- 같은 company ID master row 중복, 누락 company ID/ticker/exchange, 잘못된 alias JSON, 잘못된 version metadata를 fail-fast로 검증한다. 서로 다른 company ID의 alias collision은 `AMBIGUOUS`로 검증한다.
- directory가 외부 입력 또는 fixture 변경으로 내부 상태를 변형하지 않는지 검증한다.

### Policy and resolver

- 단일 후보는 `RESOLVED`와 ticker를 만든다.
- 서로 다른 후보 둘 이상은 `AMBIGUOUS`이며 ticker가 없다.
- 후보 없음은 `UNRESOLVED`이며 ticker가 없다.
- 같은 canonical identity의 여러 alias는 모호성으로 세지 않는다.
- `company_id`가 같은 후보는 하나의 canonical identity로 취급하고, ticker가 같다는 이유만으로 서로 다른 company ID를 병합하지 않는다.
- company 순서, 원본 `CompanyRelation`, event object identity, 빈 companies/event 입력을 검증한다.
- directory 구성 오류와 예상하지 못한 RuntimeError는 전파하는지 검증한다.
- 미등록 name은 오류가 아닌 정상 결과이며 다른 company/event resolution을 막지 않는지 검증한다.
- 같은 versioned master data와 같은 입력을 반복 100회 실행하고, CSV row·alias·candidate 반환 순서를 바꿔도 결과, 순서, company identity가 동일한지 결정성 테스트를 수행한다.

### Workflow, bootstrap, CLI

- Resolve node가 일부 ticker 없는 `ResolvedCompany`를 포함해 정상 완료하는지 검증한다.
- 중복 ticker snapshot 또는 event identity 불일치의 기존 불변식이 유지되는지 검증한다.
- Mock/OpenAI mode가 동일한 deterministic directory 및 resolver policy 계약을 사용하는지 검증한다.
- 기존 CLI JSON schema가 변경되지 않거나, 의도적으로 변경했다면 호환성 테스트와 migration note가 있는지 검증한다.

### Verification

```bash
uv run pytest
uv run python -m compileall app tests
git diff --check
```

## Implementation Preconditions

Approved Product Decision에 따라 KRX 기반 versioned local CSV의 파일 위치, 운영상 승인 주체, 데이터 version을 구현 시작 시 제공해야 한다. 구현자는 KRX 외 시장, 외부 API, 실시간 동기화, 임의의 master data 출처를 추가하지 않는다.

## Acceptance Criteria

- 입력 회사명은 확정·모호·미해결 중 정확히 하나의 상태를 가진다.
- `AMBIGUOUS`와 `UNRESOLVED`는 ticker를 만들지 않는다.
- 확정 결과는 KRX canonical identity, 영구 `company_id`, versioned local master data에 근거한다.
- Company Resolution은 LLM, prompt, stock scoring, recommendation을 호출하지 않는다.
- 원본 event identity, company 순서, Mock/OpenAI workflow 계약, Resolve 이후 흐름이 유지된다.
- 민감한 원문과 raw directory payload를 로그·CLI JSON에 기록하지 않는다.
- 모든 신규 규칙은 deterministic fake/local master data와 Policy/Workflow 테스트로 고정된다.

## Commit Message

```text
feat: add conservative company resolution
```

## Change Log

### 2026-07-29 — Approved product decision and contract hardening

- v1 지원 시장을 KRX 상장사로 확정하고, 승인된 KRX 기반 versioned local CSV만 사용하도록 범위를 고정했다.
- `company_id`를 ticker와 독립적인 영구 canonical identity로 정의하고, Business Logic의 동일성 비교 기준으로 고정했다.
- CompanyDirectory의 책임과 비책임, candidate set의 company ID 기반 중복 제거, resolution 상태 결정 규칙을 명시했다.
- Company Resolution이 Workflow에서 정확히 한 번만 실행되고 이후 단계가 immutable snapshot만 소비하는 계약을 추가했다.
- resolution 흐름도, 반복 실행 결정성 테스트, KRX CSV 필수 필드와 구현 선행 조건을 추가했다.

### 2026-07-30 — Final implementation contract

- `directory_version`은 모든 resolution observation과 resolved snapshot에 보존하고 empty directory의 version을 `empty`로 고정했다.
- canonical name을 alias와 같은 name index에 등록하고, candidate count를 distinct company ID 수로 정의했다.
- 서로 다른 company ID의 alias collision은 configuration error가 아닌 `AMBIGUOUS` 후보로 보존하도록 변경했다.
- KRX ticker 6자리 문자열, `KOSPI`/`KOSDAQ`/`KONEX` exchange enum, opaque stable company ID 및 strict alias JSON 규칙을 확정했다.
- `AMBIGUOUS`·`UNRESOLVED`는 snapshot에는 남기되 종목 evidence aggregation, score, recommendation에서는 제외하도록 확정했다.
