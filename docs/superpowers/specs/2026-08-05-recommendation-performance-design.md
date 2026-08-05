# 추천 가격 스냅샷·성과 대시보드 설계

## 목적

정기 RSS 추천 실행에서 생성된 매수·매도 후보에 대해 추천 당시의 실제 시장 가격을 영속화하고, 이후의
최신 가격과 비교한 사후 성과를 대시보드에 표시한다. 이는 자동 매매나 미래 가격 예측이 아니라 추천의
사후 관측 가능성과 설명 가능성을 높이기 위한 기능이다.

사용자 승인 정책은 다음과 같다.

1. 한국투자증권(KIS) API의 실시간 가격을 우선 조회한다.
2. 실시간 가격을 얻지 못하면 KRX OpenAPI의 가장 가까운 거래일 종가를 사용한다.
3. 두 가격을 모두 얻지 못해도 추천 실행은 성공으로 유지하고, 가격 미확인 상태와 제한된 원인만
   영속화한다.

모든 사용자 표시 시각은 `Asia/Seoul`(KST)이며, DB의 절대 시각은 UTC로 저장한다.

## 범위와 제외 범위

포함 범위는 다음과 같다.

- BUY와 SELL 추천별 가격 스냅샷 및 가격 조회 상태 저장
- KIS 실시간 → KRX 종가의 명시적 fallback
- 최신 가격을 기준으로 한 평가손익·집계 통계
- 정기 실행·수동 대시보드 실행의 추천 가격 저장
- 대시보드의 추천별 수익률 문구와 성과 통계
- `.env` 기반 KIS 설정과 운영 문서

다음은 제외한다.

- 주문 전송, 자동 매매, 보유 수량·수수료·세금 계산
- 가격 예측·백테스트 수익 보장·투자 자문
- 장중 가격을 초단위로 연속 수집하는 ticker feed
- 원문 기사·prompt·API secret을 DB/로그/UI에 보관하는 행위

## 대안과 선택

### A. KIS 실시간 + KRX 종가 fallback (선택)

KIS의 인증된 실시간 현재가를 우선 사용하되 인증, 장 마감, 네트워크, 응답 검증 실패 시 KRX의 직전
거래일 종가를 조회한다. 새 KIS credential이 필요하지만, 이미 KRX directory용으로 사용하는 공식
market-data 경계와 분리된 adapter로 유지할 수 있고, 어떤 가격이 쓰였는지를 정직하게 표시할 수 있다.

### B. KRX 종가만 사용

추가 credential이 없고 단순하지만, 사용자가 요구한 실시간 우선 원칙을 충족하지 못한다.

### C. 제3자 시세 서비스 사용

구현은 쉬울 수 있으나 데이터 재배포 약관, 키·비용·장애 책임이 추가된다. 현재 프로젝트의 KRX 상장사
범위와 사용자 승인 원칙에 비해 이점이 작다.

따라서 A를 채택한다.

## 구성과 책임 경계

```text
추천 후보 (BUY/SELL, resolved KRX ticker)
        ↓
Harness-owned RecommendationPriceRecorder
        ├── KISRealtimePriceClient
        └── KrxClosingPriceClient (fallback)
        ↓
PriceSnapshot / PriceLookupFailure
        ↓
PostgreSQL repository
        ↓
PerformanceQueryService → Dashboard DTO / Telegram 안전 요약
```

- `app/models/`은 immutable Pydantic 가격·성과 Domain 계약만 둔다.
- KIS/KRX HTTP adapter는 외부 응답을 transport DTO로만 반환하며 Domain 또는 DB를 직접 변경하지 않는다.
- Parser는 가격, 통화, 종목 코드, 거래일, 시각을 검증하고 회복 가능한 오류를 제한된 error kind로
  변환한다.
- Policy는 가격 제공자 선택이나 네트워크를 호출하지 않는다. 수익률 산식과 표시 가능 여부만 결정한다.
- Harness가 추천 결과와 price observation을 연결하고 repository에 저장한다.
- PostgreSQL adapter만 DB I/O를 수행한다. Workflow, Provider, Parser, Policy, LLM은 DB를 직접 호출하지
  않는다.

## 설정과 보안

새 설정은 다음처럼 `.env`에서만 읽는다.

```text
KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCOUNT_PRODUCT_CODE=01
KIS_BASE_URL=https://openapi.koreainvestment.com:9443
KIS_TIMEOUT_SECONDS=10
```

KIS key/secret은 선택 사항이다. 둘 중 하나만 설정된 경우 설정 오류로 기록하고 KRX fallback만 시도한다.
둘 다 없는 경우에도 worker는 정상 동작하며 실시간 단계는 `not_configured` 관측으로 남는다. credential,
authorization header, HTTP body, 원문 응답은 로그·DB·SSE·Telegram에 남기지 않는다.

KRX 종가 fallback은 기존 `KRX_API_KEY`를 사용한다. KRX 응답의 해당 종목 가격이 없거나 휴장일인 경우
정해진 lookback 범위에서 가장 최근 거래일을 찾는다. lookback을 모두 소진하면 가격 미확인으로 남긴다.

## 데이터 계약과 영속화

추천별 가격 record는 최소 다음을 보관한다.

- recommendation execution ID와 recommendation 결정 identity
- canonical company ID, 6자리 ticker, BUY/SELL action
- 가격 값, KRW 통화, `REALTIME` 또는 `CLOSE` basis, provider, 관측 UTC 시각, 기준 거래일
- `AVAILABLE`, `UNAVAILABLE` 상태와 제한 enum error kind
- 재조회와 감사에 필요한 immutable provider payload fingerprint(원문값 제외)

가격이 성공한 recommendation만 entry price를 갖는다. 가격 실패를 `0` 또는 임의의 추정값으로 저장하지
않는다. 같은 추천에는 하나의 entry snapshot만 존재하며 재실행은 중복 저장하지 않는다.

성과 조회는 entry snapshot과 최신 조회 snapshot을 비교한다. BUY 수익률은
`(latest - entry) / entry * 100`, SELL 수익률은 `(entry - latest) / entry * 100`으로 계산한다. 0 또는
음수 가격, 다른 통화, ticker 불일치, 최신 가격 미확인은 성과 미확인으로 처리한다. 수수료·배당·권리락은
포함하지 않으며 UI와 문서에 사후 단순 가격 비교라고 명시한다.

## 실행 흐름·실패 처리

1. candidate-selection이 선택한 BUY/SELL recommendation의 resolved KRX ticker를 Harness에 전달한다.
2. Harness는 각 ticker를 독립 item으로 KIS 실시간 adapter에 요청한다.
3. KIS transport/auth/rate-limit/invalid-payload/error 응답은 제한된 관측으로 만들고, 해당 item만 KRX
   종가 adapter로 전달한다.
4. KRX가 가장 가까운 거래일 종가를 반환하면 `CLOSE` snapshot을 저장한다.
5. 두 adapter 모두 실패하면 `UNAVAILABLE` record를 저장하며 sibling recommendation과 실행 결과는 보존한다.
6. dashboard 성과 조회도 같은 우선순위로 최신 가격을 읽되, entry price record를 수정하지 않고 별도
   evaluation snapshot을 저장하거나 계산 시점 DTO로 안전하게 투영한다.

일시적 timeout/connection/429/5xx 오류는 adapter 범위에서 bounded exponential backoff로 재시도한다.
인증 실패, 잘못된 ticker, schema 검증 실패는 재시도하지 않는다. retry 횟수와 제한 error kind만 감사에
저장한다.

## UI와 Telegram

대시보드 추천 행은 가격이 있을 때 다음을 표시한다.

```text
추천 기준: KIS 실시간 72,000원 (2026-08-05 09:15 KST)
그날 샀더라면 현재 +3.4%
```

SELL은 `그날 팔았더라면 현재 +N%`로 short-direction 사후 비교임을 표시한다. 가격이 없으면
`가격 미확인`과 basis/provider의 제한 상태만 표시하며 수익률을 만들지 않는다. 전체 통계는 가격 확인
추천 수, 미확인 수, BUY/SELL별 승률, 평균·중앙 수익률, 최신 평가 시각을 제공한다.

Telegram은 완료 요약에 후보명·ticker·action·추천 기준 가격·basis만 포함하며, 성과 통계와 기술적 오류
전문은 포함하지 않는다.

## 테스트와 검증

- KIS 설정의 누락·부분 설정·secret 비노출을 단위 테스트한다.
- KIS 정상 응답, 인증/429/timeout/schema 오류, bounded retry를 테스트한다.
- KRX 종가 fallback, 휴장일 lookback, 두 제공자 모두 실패의 부분 성공을 테스트한다.
- recommendation과 가격 record의 중복 방지, UTC/KST 시각 투영, DB migration과 repository 조회를 테스트한다.
- BUY/SELL 수익률, 0/미확인 가격, 통화/ticker 불일치, 평균·중앙·승률 집계를 테스트한다.
- 대시보드/API 응답이 가격·성과를 올바로 표시하되 secret·raw payload를 내보내지 않는지 테스트한다.
- 전체 pytest, compileall, git diff --check, Docker migration/worker smoke test를 수행한다.

## 변경 이력

- 2026-08-05: 사용자가 KIS 실시간 가격 우선, 조회 불가 시 종가 fallback을 승인했다. 기존 scheduled
  recommendation PR과 분리된 `codex/recommendation-performance` 변경 단위에서 구현한다.
