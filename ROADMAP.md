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

**Status:** Completed

## 목적

추출 event의 회사명을 KRX 상장사의 신뢰할 수 있는 canonical company identity로 해석한다.

## 완료 조건

동명이인, ticker 변경, 미해결 회사를 명시적으로 다루고 가짜 ticker를 만들지 않는다. v1은 approved KRX 기반 versioned local CSV와 KRX OpenAPI snapshot을 모두 지원하며, API mode는 KOSPI·KOSDAQ·KONEX을 실행 시작 시 동기화한다.

## 산출물

KRX local/API master-data directory, 영구 company identity, resolution 관측 모델, provenance, 보수적 aggregation 정책 및 결정성 테스트.

# Phase 6 — Impact Analysis

**Status:** Completed

## 목적

검증된 event가 기업·산업·시장·거시경제에 미치는 영향을 근거와 함께 분석한다.

## 완료 조건

영향 결과가 event, validation, company mapping 근거로 추적 가능하며 LLM을 사용해도 최종 해석은 Policy/strategy가 소유한다.

## 산출물

확장 impact Domain, evidence-aware analysis strategy, 방향·불확실성 정책, 테스트 가능한 deterministic baseline.

# Phase 7 — Stock Scoring

**Status:** Completed

## 목적

검증된 근거, 최신성, 신뢰도, impact를 투명한 종목 점수로 집계한다.

## 완료 조건

score factor, 가중치, 경계값이 명시적 Policy로 관리되고 같은 입력에서 재현된다.

## 산출물

scoring factor contract, aggregation strategy, 설정 가능한 Policy, 회귀 테스트와 설명 가능한 score breakdown.

# Phase 8 — Explainable Recommendation & Candidate Selection

**Status:** Completed

## 목적

종목 점수를 기존 다섯 recommendation action으로 연결하고, 결정된 action의 정책 근거와 후보 선택 결과를 immutable Domain으로 보존한다.

## 완료 조건

기존 threshold boundary 및 CLI JSON schema를 유지하면서 action·reason code·threshold snapshot, deterministic candidate rank·exclusion을 설명 가능하게 보존한다.

## 산출물

explainable recommendation policy, threshold snapshot, result-level provenance, exhaustive ranking catalog, candidate-selection audit trail, regression tests.

# Phase 9 — 운영 안정성 및 자동화

**Status:** Completed

## 목적

매일 실행되는 수집·분석 작업을 재현, 감사, 복구 가능한 운영 시스템으로 만든다.

## 완료 조건

UTC daily scheduler, JSONL persistence/audit·metrics·alerting, request-cap cost guard, latency threshold, secret-safe logging과 retention/recovery plan이 Harness 중심으로 운영된다.

## 산출물

실행 scheduler, 보안 관측 체계, 품질 지표, 장애 대응 문서, 데이터 보존 정책.

## v1 운영 범위 제한

외부 notification provider, OS cron/service installation, distributed lock, token-price accounting, object storage, automatic deletion은 안정된 Harness 계약 위의 후속 운영 통합이다. v1은 안전한 JSONL adapter와 explicit configuration만 제공하며, 자동 삭제나 비밀값 전송을 하지 않는다.

# 후속 운영 확장 — 투자 테마·뉴스 주제 수집 조건

**Status:** In Progress

대시보드는 반도체·AI·대체에너지 같은 투자 테마와 뉴스 주제를 함께 선택해 수집 결과를 좁힌다. 카탈로그
기반의 결정적 filter, PostgreSQL 실행 조건 snapshot, 점수표·과거 실행·가격 성과·KST 스케줄·Telegram·실행
그래프는 작은 독립 변경 단위로 확장한다. LLM은 테마/주제 filter나 매수·매도 결정을 직접 내리지 않는다.

정기 실행 설정·KST worker·Telegram terminal 요약과 추천 시점 가격 snapshot, 이후 수익률·"그날 샀더라면"
대시보드는 현재 구현 단위에 포함한다. 가격은 KIS 실시간 현재가를 우선하고 KRX 최근 거래일 종가로 fallback하며,
KIS 미설정·휴장일·외부 오류는 recommendation 실행을 중단하지 않는 `가격 미확인` 관측으로 남긴다. 성과는
수수료·세금·배당을 제외한 사후 단순 가격 비교로 제한한다.
