# 제품 로드맵

## 운영 원칙

로드맵은 PR 번호가 아닌 기능 phase를 기준으로 관리한다. 각 phase의 세부 PR은 시작 전 `docs/`에 계획으로 작성하며, `PROJECT_GUIDE.md`의 Non Goals와 LLM/Parser/Policy 책임 분리를 지켜야 한다.

# Phase 1 — News Collection 및 Normalization

**Status:** Completed

## 목적

여러 community/provider의 원본 데이터를 공통 처리 경로로 수집하고 표준화한다.

## 완료 조건

Provider 실패가 다른 source를 막지 않고, `RawPost → NormalizeResult → Post/Article` 흐름이 공통 계약으로 동작한다.

## 산출물

Provider/Normalizer registry, core Skill contract, 수집·정규화 오류 관측, 결정적 테스트 경로.

# Phase 2 — Event Extraction

**Status:** Completed

## 목적

정규화된 기사를 투자 분석 가능한 `NewsEvent`로 구조화한다.

## 완료 조건

Mock과 OpenAI extraction이 같은 workflow contract를 사용하고, malformed event가 정상 sibling을 막지 않는다.

## 산출물

NewsEvent Domain, extraction Parser, structured-output adapter, PromptBuilder, batch 오류 관측.

# Phase 3 — AI Screening

**Status:** Completed

## 목적

이벤트의 relevance, importance, credibility 관측을 생성하고 Policy가 처리 우선순위를 결정하게 한다.

## 완료 조건

점수는 0–100 Domain int 계약을 지키고, `ScreeningPolicy`만 ACCEPT/REVIEW/REJECT를 결정한다.

## 산출물

Screening DTO/Parser, 부분 성공 계약, 결정적 Mock Screener, OpenAI Screener, 안전한 로그.

# Phase 4 — Cross Validation 및 Resolve

**Status:** Completed

## 목적

REVIEW 이벤트를 다른 기사와 비교해 근거 관계를 만들고, Policy가 검증 상태와 resolve 결론을 결정하게 한다.

## 완료 조건

LLM은 relation만 반환하며 independent source와 final status는 Policy가 보수적으로 계산한다. 검증 결과 일부가 없어도 Resolve가 유효 decision으로 완료된다.

## 산출물

Cross-validation Parser/Policy, 연결 요소 기반 출처 계산, Resolve policy, OpenAI/Mock validator, CLI mode 조립.

# Phase 5 — Company Resolution

**Status:** Planned

## 목적

추출 event의 회사명을 신뢰할 수 있는 ticker/company identity로 해석한다.

## 완료 조건

동명이인, ticker 변경, 복수 상장, 미해결 회사를 명시적으로 다루고 가짜 ticker를 만들지 않는다.

## 산출물

외부 company lookup adapter, resolution 관측 모델, provenance, partial-failure Policy 및 테스트.

# Phase 6 — Impact Analysis

**Status:** Planned

## 목적

검증된 event가 기업·산업·시장·거시경제에 미치는 영향을 근거와 함께 분석한다.

## 완료 조건

영향 결과가 event, validation, company mapping 근거로 추적 가능하며 LLM을 사용해도 최종 해석은 Policy/strategy가 소유한다.

## 산출물

확장 impact Domain, evidence-aware analysis strategy, 방향·불확실성 정책, 테스트 가능한 deterministic baseline.

# Phase 7 — Stock Scoring

**Status:** Planned

## 목적

검증된 근거, 최신성, 신뢰도, impact를 투명한 종목 점수로 집계한다.

## 완료 조건

score factor, 가중치, 경계값이 명시적 Policy로 관리되고 같은 입력에서 재현된다.

## 산출물

scoring factor contract, aggregation strategy, 설정 가능한 Policy, 회귀 테스트와 설명 가능한 score breakdown.

# Phase 8 — Portfolio Recommendation

**Status:** Planned

## 목적

종목 점수를 사용자에게 이해 가능한 buy/watch/caution 관찰과 포트폴리오 수준 제약으로 연결한다.

## 완료 조건

추천은 근거·불확실성·위험 제약을 함께 설명하고 자동 거래를 수행하지 않는다.

## 산출물

recommendation Policy, risk/profile input model, portfolio constraint strategy, 사용자 출력과 제품 고지.

# Phase 9 — 운영 안정성 및 자동화

**Status:** Planned

## 목적

매일 실행되는 수집·분석 작업을 재현, 감사, 복구 가능한 운영 시스템으로 만든다.

## 완료 조건

스케줄 실행, persistence, metrics, audit trail, alerting, 비용·latency·secret 관리가 Harness 중심으로 운영된다.

## 산출물

실행 scheduler, 보안 관측 체계, 품질 지표, 장애 대응 문서, 데이터 보존 정책.
