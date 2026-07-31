# PR29a: Event Classification Foundation

## Summary

PR29a는 PR30 Impact Analysis 전에 `NewsEvent`의 공통 분류 계약을 추가한다. EventType은
Impact에 종속되지 않는 필수 상위 Domain Category이며, EventFact는 선택적·복수의 독립 사건이다.
PR30 Impact Rule Catalog는 제목·요약·keywords를 다시 해석하지 않고 이 EventFact만 소비한다.

## Scope

- `NewsEvent`에 필수 `event_type`과 immutable `event_facts`를 추가한다.
- extractor transport DTO, Parser, prompt, Mock extractor를 같은 구조화 계약으로 갱신한다.
- EventType 오류와 EventFact 오류의 부분 성공 경계를 구분한다.
- PR30 문서와 장기 Domain/Workflow/LLM 계약을 선행 분류 계약에 맞춘다.

## Non Goals

- Impact observation, ImpactPolicy, aggregation, scoring, recommendation 구현
- 자유 텍스트로 Impact direction을 판단하는 규칙 추가
- CLI output, OpenAI client/adapter 구조, 외부 데이터 연동 변경
- `OTHER` EventType fallback 또는 EventFact 기반 투자 판단

## Domain Contract

### EventType

EventType은 사건의 상위 Domain Category이며, Impact Analysis 전용 분류가 아니다. 초기 값은
`CORPORATE_EVENT`, `LEGAL_EVENT`, `FINANCIAL_EVENT`, `PRODUCT_EVENT`, `MACRO_EVENT`다.

- EventType은 모든 NewsEvent에 반드시 하나 존재한다.
- 새 EventFact가 기존 Category에 수용되면 EventType을 추가하지 않는다.
- EventType은 새로운 개별 사건이 아니라 새로운 상위 Domain Category가 필요할 때만 추가한다.
- Type을 결정하지 못한 LLM event는 recoverable event validation 오류로 처리하고 후속 단계에
  전달하지 않는다.

### EventFact

EventFact는 EventType 안의 구체적이고 독립적인 사건이다. 초기 값은
`FACTORY_EXPANSION`, `MASS_LAYOFF`, `BANKRUPTCY`, `PRODUCT_RELEASE`, `CEO_INTERVIEW`다.

- EventFact는 선택적이며 하나의 NewsEvent는 복수 Fact를 가질 수 있다.
- Fact는 원본 extraction 순서를 보존한다. 동일 Fact는 첫 등장만 남기며 이후 중복은 오류 없이
  정규화로 제거한다.
- 여러 Fact를 복합 Fact로 합치거나 새 의미를 추론하지 않는다. Consumer와 PR30 Rule Catalog는
  각 Fact에 독립적으로 동작한다.
- EventType과 EventFact의 호환성은 Enum 내부가 아닌 별도 immutable `EventTypeCompatibility`
  table이 소유한다. Parser는 주입된 table로 Fact를 검증하며, 향후 Rule Set 또는 Consumer는
  Domain Enum을 바꾸지 않고 table을 교체할 수 있다.
- Compatibility 정책은 table별로 교체할 수 있지만, 하나의 table 안에서 각 EventFact는 정확히
  하나의 EventType에만 귀속되고, EventFact Enum의 모든 값이 반드시 한 번씩 등록된다. 동일 Fact를
  여러 Type entry에 등록하거나 Fact를 누락하면 table 생성이 fail-fast한다.
- EventType은 event의 주된 Category이며 Fact는 주입된 compatibility table에서 해당 Type과
  호환되어야 한다. 서로 다른 상위 Category의 복합 사건은 Extractor가 별도 NewsEvent로 분리한다.
- `BANKRUPTCY`를 EventType에 영구 귀속하지 않는다. v1 default table에서만
  `FINANCIAL_EVENT`와 호환되는 Fact로 등록한다.
- EventType만 있고 EventFact가 없는 값은 유효한 Domain Event다. 다만 PR30 Rule Catalog의 입력
  조건을 충족하지 않아 Impact observation을 만들지 않는다.

## Parser and Prompt Contract

- structured response의 `event_type`은 required string이며 Parser가 EventType enum으로 검증한다.
- `event_facts`는 optional string list이며 Parser가 각 값을 독립적으로 enum 및 Type 호환성으로
  검증한다.
- 잘못된 Type은 event 전체를 제외하는 `EVENT_VALIDATION` 오류다.
- 잘못된 Fact는 유효 event와 sibling Fact를 보존하고 `FACT_VALIDATION`, event index, fact index를
  기록한다.
- Prompt는 기사에 명시된 Type/Fact만 반환하고, 사건을 합치거나 ticker·투자 판단을 추론하지
  않도록 지시한다.

## PR30 Integration

PR30 Strategy는 `DIRECT` 회사와 등록된 EventFact 조합마다 독립 observation을 생성한다.
`INDIRECT` 회사와 Fact 없는 event에는 observation을 만들지 않는다. 상충 Fact는 각각의
observation으로 보존하며, ImpactPolicy는 이를 변경하지 않고 filtering만 수행한다. Aggregation은
eligible observation만 downstream evidence로 선택한다.

## Test Plan

- EventType 필수성, Fact 순서·중복 정규화·Type 호환성을 검증한다.
- 유효 Type과 빈 Fact 목록을 보존하고 invalid Type이 event-local 오류인지 검증한다.
- 일부 invalid Fact가 event와 valid Fact를 보존하며 fact-local 오류를 만드는지 검증한다.
- Prompt, transport DTO, Parser, Mock extractor의 계약 일치와 Workflow identity 보존을 검증한다.
- 전체 pytest, compileall, diff check를 실행한다.

## Commit Message

```text
feat: add event classification contract
```

## Change Log

### 2026-07-30 — Approved implementation contract

- EventType을 필수 상위 Domain Category로, EventFact를 선택적 복수의 독립 사건으로 확정했다.
- Type 오류와 Fact 오류의 부분 성공 경계, 중복·순서 보존, Fact 없는 유효 event의 의미를 고정했다.
- PR30이 EventFact만 Rule Catalog 입력으로 소비하도록 선행 계약을 정의했다.

### 2026-07-30 — Implementation completed

- immutable EventType/EventFact Domain, strict transport fields, fact-local Parser 오류 관측과
  deterministic Mock extraction을 구현했다.
- 기존 Event fixture와 parser/prompt 회귀 테스트를 새 필수 Type 계약에 맞추고, 전체 테스트·컴파일·diff
  검증을 통과했다.

### 2026-07-30 — Compatibility policy extraction

- EventFact Enum에서 EventType 참조와 호환성 메서드를 제거했다.
- immutable EventTypeCompatibility table을 추가하고 Parser가 생성자 주입으로 이를 검증하도록
  변경했다. 기본 table과 교체 가능한 table의 동작을 테스트로 고정했다.

### 2026-07-30 — Single fact ownership per table

- Compatibility table validator가 모든 entry의 Fact를 평탄화해, 하나의 table 안에서 같은 Fact가
  여러 EventType에 귀속되면 fail-fast하도록 보완했다.

### 2026-07-30 — Complete fact coverage per table

- Compatibility table이 각 EventFact를 정확히 한 번 등록하도록 강화했다. 누락된 Fact는 이름을
  포함한 fail-fast 오류로 반환한다.
