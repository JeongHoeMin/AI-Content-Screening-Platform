# 로드맵

## 현재 기준선

PR1–PR28에서 core contract, provider/normalization, content pipeline, LangGraph workflow, 결정적 downstream, OpenAI 기반 event extraction/screening/cross validation, CLI/bootstrap을 구현했다. 현재 OpenAI는 이벤트 관측 단계까지만 담당하고, ticker resolver·impact·aggregation·scoring·recommendation은 결정적 구현과 static lookup 기반으로 동작한다.

아래 순서는 제품 목표를 향한 계획이며, 각 PR은 시작 전에 `docs/`에 승인된 계획을 작성하고 현재 계약과 운영 데이터에 맞춰 세부 범위를 확정한다.

## PR29 — Company Mapping 신뢰성 강화

- 정적 ticker lookup을 실제 company/ticker resolution adapter로 확장한다.
- 동명이인, ticker 변경, 복수 상장, 미해결 회사의 관측 결과를 명시한다.
- resolution confidence와 근거를 Domain/Policy 경계에 맞게 설계한다.
- 외부 provider 실패가 전체 Workflow를 중단하지 않도록 부분 성공을 유지한다.

완료 기준: `ResolvedNewsEvent`가 검증 가능한 회사 매핑 관측을 가지며, 미해결 event는 가짜 ticker 없이 정책적으로 처리된다.

## PR30 — Evidence 기반 Impact Analysis

- 기업·산업·시장·거시경제 영향 모델을 확장한다.
- LLM을 쓴다면 영향 관측과 근거만 반환하고, 방향·점수의 최종 해석은 Policy/strategy가 수행한다.
- event, cross-validation, company mapping 근거가 분석 결과에 추적 가능하게 연결된다.

완료 기준: 분석 결과가 원인과 근거를 보존하며, 투자 조언이나 Policy 판단을 LLM에 위임하지 않는다.

## PR31 — Stock Scoring 및 Recommendation 고도화

- 증거 집계, 최신성, 신뢰도, impact를 명시적 scoring factor로 정리한다.
- Recommendation은 score와 위험 규칙에 근거해 buy/watch/caution 등 제품 상태를 생성한다.
- 점수/추천 임계값은 설정 가능하되 재현 가능한 Policy 테스트로 고정한다.

완료 기준: 사용자 출력이 종목, 이유, 출처 근거, 불확실성을 함께 설명하고 동일 입력에서 재현된다.

## PR32 — 실데이터 News Collection 운영화

- RSS, 공시, 신뢰할 수 있는 뉴스 provider를 registry 기반으로 추가한다.
- 수집 시간, 중복 제거, normalize 오류, source 품질을 관측한다.
- rate limit, timeout, provider 장애와 재시도 정책을 Harness 경계에서 다룬다.

완료 기준: provider 하나의 실패가 전체 수집을 막지 않고, 입력 provenance가 추적된다.

## PR33 — Portfolio Optimization 및 사용자 경험

- 단일 종목 추천을 포트폴리오 수준 제약과 위험 분산으로 확장한다.
- 사용자 risk profile, 보유 종목, 노출 한도는 명시적인 입력 모델과 Policy로 다룬다.
- 결과는 설명 가능하고 투자 자문으로 오인되지 않도록 제품 고지를 포함한다.

완료 기준: recommendation을 비중·제약·근거와 함께 제시하고, 무단 거래 실행을 하지 않는다.

## PR34 — 운영 안정성 및 품질 관리

- scheduled run, persistence, audit trail, metrics, alerting을 Harness 중심으로 도입한다.
- prompt/model version, parser 오류율, provider 품질, policy outcome을 민감정보 없이 관측한다.
- 데이터 보존·삭제, secret 관리, 비용/latency budget을 운영 정책으로 정한다.

완료 기준: 매일 자동 실행이 재현·감사·복구 가능하며, 실패가 안전하게 격리되고 운영자가 원인을 파악할 수 있다.

## 단계별 공통 게이트

- `PROJECT_GUIDE.md`의 LLM/Parser/Policy 분리와 부분 성공을 유지한다.
- Mock mode 및 CLI JSON 계약을 의도적 버전 변경 없이는 깨지 않는다.
- 모든 새 외부 경계에는 Pydantic validation, 제한 로그, fake 기반 테스트를 둔다.
- 실제 투자 데이터와 모델 출력에 대한 장기 평가 기준은 운영 데이터가 축적된 뒤 별도 decision log로 확정한다.
