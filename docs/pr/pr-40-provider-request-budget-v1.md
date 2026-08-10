# PR-40 — Provider Request Budget v1

## 목표

실제 provider usage/가격 응답이 없는 현재 structured-output 경계에서, 실행당 OpenAI provider request 수를 강제해 비용 상한을 보수적으로 관리한다.

## 범위

- `OPENAI_MAX_REQUESTS_PER_EXECUTION` 설정과 immutable request budget을 추가한다.
- budgeted structured-output adapter가 provider 호출 전 atomically claim하고 limit 초과 시 provider를 호출하지 않는다.
- workflow execution Harness가 context-local budget scope를 열어 extractor/screener/cross-validator가 한 실행의 동일 상한을 공유한다.
- mock mode는 budget을 조립하지 않는다.

## 비범위

- token usage/원화·달러 비용 추정, provider 가격표, rate limit, daily/monthly shared quota, retries, dashboard는 후속 작업이다.

## 설계 결정

1. request budget은 비용의 정확한 대체값이 아니라 hard upper bound다.
2. scope는 context-local이라 concurrent executions가 count를 공유하지 않는다.
3. claim은 SDK call 전에 이뤄져 limit 초과가 비용을 유발하지 않는다.

## 변경 이력

- 2026-07-30: 최초 계획 작성. 실제 token telemetry가 도입되기 전까지 provider request 수를 안전한 비용 proxy로 사용한다.
