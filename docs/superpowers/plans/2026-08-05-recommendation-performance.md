# 추천 가격 스냅샷·성과 대시보드 Implementation Plan

**Status:** Completed

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** KIS 실시간 현재가를 우선 기록하고 KRX 종가로 fallback하여, 추천별 사후 가격 성과와 통계를 안전하게 저장·표시한다.

**Architecture:** 외부 KIS/KRX adapter는 관측만 하고 Parser가 immutable Pydantic 가격 모델로 검증한다. RecommendationPriceRecorder Harness가 가격 관측을 PostgreSQL에 저장하고, 대시보드는 repository 결과를 성과 Policy로 투영한다.

**Tech Stack:** Python 3.9+, Pydantic v2, SQLAlchemy async/asyncpg, Alembic, FastAPI, PostgreSQL, pytest.

## Global Constraints

- 모든 Python 함수·메서드·변수·반환값에 명시적 type hint를 작성한다.
- 외부 입력·설정·DTO·Domain은 Pydantic을 사용하고 Domain 모델은 immutable이다.
- Provider/Parser/Policy/Workflow는 DB를 호출하지 않으며 Harness-owned persistence adapter만 DB I/O를 수행한다.
- structlog만 사용하며 secret, authorization header, HTTP 원문, 기사 원문, prompt, 예외 전문을 남기지 않는다.
- UI/Telegram 시각은 Asia/Seoul, DB timestamp는 UTC를 사용한다.
- 실시간 가격 실패/미설정 시 KRX 최근 거래일 종가, 둘 다 실패하면 UNAVAILABLE이고 가격 실패는 추천 실행 실패가 아니다.
- timeout/connection/429/5xx만 최초 호출 뒤 1초·2초 간격으로 최대 3회 재시도한다. auth·schema·unknown ticker는 재시도하지 않는다.

---

## 파일 구조

| 파일 | 책임 |
| --- | --- |
| app/models/market_price.py | 가격 basis/status/error/snapshot/성과 Domain |
| app/config/market_data.py | KIS 선택 설정과 KRX 가격 lookback |
| app/market_prices/{contracts,kis,krx,parser,service,performance}.py | 외부 시세 adapter, fallback, 수익률 Policy |
| app/persistence/price_repository.py | 가격 snapshot SQLAlchemy repository |
| app/harness/recommendation_prices.py | 후보별 entry/latest price orchestration |
| app/persistence/schema.py, alembic/versions/20260805_04_recommendation_price_snapshots.py | additive storage |
| app/web/app.py, app/web/dashboard_html.py | performance DTO/API/화면 |
| app/harness/telegram.py | 가격 기준을 포함한 안전한 정기 알림 |

### Task 1: 가격 Domain과 설정

**Files:** Create `app/models/market_price.py`; modify `app/models/__init__.py`, `app/config/market_data.py`, `app/config/__init__.py`; test `tests/test_market_price_models.py`, `tests/test_market_price_config.py`.

**Interfaces:** `PriceBasis`, `PriceSnapshotStatus`, `PriceProvider`, `PriceErrorKind`, `RecommendationPriceSnapshot`, `RecommendationPerformance`, `KisConfig`, `load_optional_kis_config() -> KisConfig | None`.

- [ ] **Step 1: 실패 test를 작성한다.** `AVAILABLE` snapshot에 price=None을 전달하면 ValidationError이고, KIS_APP_KEY만 설정한 경우 `load_optional_kis_config()`이 key 값을 포함하지 않는 ConfigurationError를 내는 test를 작성한다.
- [ ] **Step 2: 실패를 확인한다.** Run: `python -m pytest tests/test_market_price_models.py tests/test_market_price_config.py -v`. Expected: module/loader 부재로 FAIL.
- [ ] **Step 3: 최소 계약을 구현한다.** snapshot은 run_id, recommendation_index >= 0, 6자리 ticker, BUY/SELL action, status, Decimal price, basis/provider, UTC observed_at, trading_date, bounded error_kind를 갖는다. AVAILABLE은 양수 price와 basis/provider/trading_date, UNAVAILABLE은 이 값들의 null과 error_kind를 강제한다. KisConfig는 SecretStr key/secret, base URL, product code, timeout을 갖고 둘 다 비어 있으면 None, 하나만 있으면 ConfigurationError다.
- [ ] **Step 4: test를 통과시킨다.** Run: `python -m pytest tests/test_market_price_models.py tests/test_market_price_config.py -v`. Expected: PASS.
- [ ] **Step 5: 커밋한다.** `git add app/models/market_price.py app/models/__init__.py app/config/market_data.py app/config/__init__.py tests/test_market_price_models.py tests/test_market_price_config.py && git commit -m 'feat: add market price contracts and KIS config'`.

### Task 2: KIS/KRX adapter와 fallback

**Files:** Create `app/market_prices/__init__.py`, `contracts.py`, `kis.py`, `krx.py`, `parser.py`, `service.py`; test `tests/test_kis_market_price_client.py`, `tests/test_krx_market_price_client.py`, `tests/test_market_price_service.py`.

**Interfaces:** `KisRealtimePriceClient.fetch(ticker, observed_at)`, `KrxClosingPriceClient.fetch(ticker, observed_at)`, `MarketPriceService.capture(ticker, observed_at)` return immutable `PriceLookupObservation`.

- [ ] **Step 1: 실패 test를 작성한다.** KIS TRANSPORT error 뒤 KRX 72000원/2026-08-04 종가가 AVAILABLE/CLOSE/KRX로 반환됨, invalid ticker는 재시도하지 않음, KRX 휴장일은 lookback하는 test를 작성한다.
- [ ] **Step 2: 실패를 확인한다.** Run: `python -m pytest tests/test_kis_market_price_client.py tests/test_krx_market_price_client.py tests/test_market_price_service.py -v`. Expected: price client/service 부재로 FAIL.
- [ ] **Step 3: adapter와 Parser를 구현한다.** KIS는 `/oauth2/tokenP` token cache와 `/uapi/domestic-stock/v1/quotations/inquire-price`의 `output.stck_prpr`만 검증한다. KRX는 `stk_bydd_trd`, `ksq_bydd_trd`, `knx_bydd_trd`에서 ticker matching row의 `TDD_CLSPRC`만 검증한다. raw payload/token/error text는 반환·로그에 넣지 않는다.
- [ ] **Step 4: fallback을 구현한다.** KIS success는 즉시 반환한다. KIS unavailable은 KRX 7일 lookback으로 넘긴다. TRANSPORT/RATE_LIMIT/SERVER만 injected sleep(1, 2초)으로 재시도한다. KIS 미설정은 NOT_CONFIGURED 관측 후 KRX를 즉시 호출하며 두 source 실패는 하나의 bounded unavailable을 반환한다.
- [ ] **Step 5: test를 통과시킨다.** 위 focused pytest가 PASS해야 하며 KIS success/config 없음/timeout/429/auth 미재시도/KRX 휴장 fallback/두 실패를 포함한다.
- [ ] **Step 6: 커밋한다.** `git add app/market_prices tests/test_kis_market_price_client.py tests/test_krx_market_price_client.py tests/test_market_price_service.py && git commit -m 'feat: add KIS and KRX market price fallback'`.

### Task 3: 가격 snapshot 영속화와 Harness

**Files:** Modify `app/persistence/schema.py`, `database.py`, `harness_adapter.py`, `__init__.py`, `app/web/app.py`, `app/scheduled_worker.py`; create `app/persistence/price_repository.py`, `app/harness/recommendation_prices.py`, `alembic/versions/20260805_04_recommendation_price_snapshots.py`; test `tests/test_recommendation_price_repository.py`, `tests/test_recommendation_price_recorder.py`, `tests/test_dashboard_price_recording.py`.

**Interfaces:** `RecommendationPricePersistence.store_entries(snapshots)`; `RecommendationPriceRecorder.record_entries(run_id, recommendations, observed_at)`.

- [ ] **Step 1: 실패 test를 작성한다.** 두 BUY 후보 중 하나의 가격이 unavailable이어도 두 snapshot이 저장되는 test와 같은 entry를 두 번 기록해도 run_id/index/ENTRY가 하나인 test를 작성한다.
- [ ] **Step 2: 실패를 확인한다.** Run: `python -m pytest tests/test_recommendation_price_repository.py tests/test_recommendation_price_recorder.py tests/test_dashboard_price_recording.py -v`. Expected: table/repository/recorder 부재로 FAIL.
- [ ] **Step 3: additive schema/repository를 구현한다.** table columns은 id, run_id, recommendation_index, snapshot_kind, company_id/name, ticker, action, status, price, currency, basis, provider, observed_at, trading_date, error_kind, created_at이다. `(run_id, recommendation_index, snapshot_kind)` unique, entry는 `on_conflict_do_nothing`, migration parent는 20260805_03이다.
- [ ] **Step 4: Harness를 연결한다.** DashboardRunManager는 result build 후 terminal SSE 전 optional recorder를 best-effort 호출한다. DB 미설정/price adapter 조립 실패는 safe structlog만 남기며 실행을 실패시키지 않는다. 수동과 run_scheduled가 동일 code path를 사용한다.
- [ ] **Step 5: test를 통과시킨다.** focused pytest가 unique entry, unavailable 저장, 25-item 부분 성공, DB optional, manual/scheduled 경로를 PASS해야 한다.
- [ ] **Step 6: 커밋한다.** `git add app/persistence app/harness/recommendation_prices.py app/web/app.py app/scheduled_worker.py alembic/versions/20260805_04_recommendation_price_snapshots.py tests/test_recommendation_price_repository.py tests/test_recommendation_price_recorder.py tests/test_dashboard_price_recording.py && git commit -m 'feat: persist recommendation entry prices'`.

### Task 4: 성과 API·대시보드·Telegram

**Files:** Modify `app/market_prices/performance.py`, `app/persistence/price_repository.py`, `app/persistence/harness_adapter.py`, `app/harness/recommendation_prices.py`, `app/web/app.py`, `app/web/dashboard_html.py`, `app/harness/telegram.py`; test `tests/test_recommendation_performance.py`, `tests/test_dashboard_performance_api.py`, `tests/test_telegram_price_summary.py`.

**Interfaces:** `RecommendationPerformancePolicy.evaluate(entry, latest)` and `GET /api/recommendations/performance`.

- [ ] **Step 1: 실패 test를 작성한다.** SELL entry 100/latest 90의 return이 +10.0이고, unavailable item의 API return_percent가 null이며 수익률을 만들지 않는 test를 작성한다.
- [ ] **Step 2: 실패를 확인한다.** Run: `python -m pytest tests/test_recommendation_performance.py tests/test_dashboard_performance_api.py tests/test_telegram_price_summary.py -v`. Expected: policy/endpoint 부재로 FAIL.
- [ ] **Step 3: Policy/latest refresh를 구현한다.** BUY `(latest-entry)/entry*100`, SELL `(entry-latest)/entry*100`, Decimal half-up 0.1%를 쓴다. 0/negative, ticker/currency mismatch, latest unavailable은 null이다. latest는 entry를 수정하지 않고 `(run_id,index,LATEST)`로 upsert하며 summary는 확인/미확인, BUY/SELL 수, positive win rate, mean, median, latest time을 계산한다.
- [ ] **Step 4: DTO/UI/Telegram을 구현한다.** API는 items/summary/evaluated_at만 반환한다. Browser는 서버 계산값으로 BUY `그날 샀더라면 현재 +N.N%`, SELL `그날 팔았더라면 현재 +N.N%`, unavailable `가격 미확인`을 표시하고 entry provider/basis/KST 시각을 함께 표시한다. Telegram은 최대 10개 후보의 회사명/action/가격/basis만 포함한다.
- [ ] **Step 5: test를 통과시킨다.** focused pytest가 BUY/SELL formula, latest missing, ticker isolation, median/win rate, KST, secret/payload absence를 PASS해야 한다.
- [ ] **Step 6: 커밋한다.** `git add app/market_prices/performance.py app/persistence/price_repository.py app/persistence/harness_adapter.py app/harness/recommendation_prices.py app/web/app.py app/web/dashboard_html.py app/harness/telegram.py tests/test_recommendation_performance.py tests/test_dashboard_performance_api.py tests/test_telegram_price_summary.py && git commit -m 'feat: show recommendation performance dashboard'`.

### Task 5: 한국어 문서와 통합 검증

**Files:** Modify `README.md`, `ARCHITECTURE.md`, `DOMAIN_MODEL.md`, `TESTING_GUIDE.md`, `ROADMAP.md`, `DECISION_LOG.md`, `docs/정기-추천-및-텔레그램-운영.md`; test `tests/test_market_price_live_contract.py`.

- [ ] **Step 1: opt-in live contract test를 작성한다.** RUN_LIVE_MARKET_DATA_TESTS=1일 때 005930 가격이 AVAILABLE/양수인지 검사한다. credential이 없으면 skip하고 기본 CI pytest는 외부 API 호출을 하지 않는다.
- [ ] **Step 2: 문서를 갱신한다.** KIS env keys, KRX fallback, Docker restart, KST 표기, 가격 미확인, 수수료/세금/배당을 제외한 사후 단순 가격 비교 한계를 한국어로 기록한다. Architecture/Domain/Decision Log에는 Harness 경계와 KIS 우선 결정을, README에는 secret 없는 config names를 반영한다.
- [ ] **Step 3: 전체 검증을 실행한다.** `python -m pytest -q`; `PYTHONPYCACHEPREFIX=/private/tmp/ai-screening-pycache python -m compileall app tests`; `git diff --check`; `docker-compose config`; `docker-compose up --build -d postgres db-migrate schedule-worker`; `docker-compose ps`; 마지막으로 `docker-compose down`을 -v 없이 실행한다. Expected: pytest PASS(live test skip), compile/diff exit 0, postgres healthy, migration exit 0, worker running.
- [ ] **Step 4: 커밋한다.** `git add README.md ARCHITECTURE.md DOMAIN_MODEL.md TESTING_GUIDE.md ROADMAP.md DECISION_LOG.md docs/정기-추천-및-텔레그램-운영.md docs/superpowers/plans/2026-08-05-recommendation-performance.md tests/test_market_price_live_contract.py pyproject.toml && git commit -m 'docs: document recommendation price operations'`.

## Plan self-review

- **설계 coverage:** Task 2가 실시간/종가 fallback, Task 3이 immutable entry storage, Task 4가 BUY/SELL 성과와 UI/Telegram, Task 5가 KST·보안·문서·Docker 검증을 다룬다.
- **Placeholder scan:** 남겨둔 미결 항목이나 모호한 오류 지시를 두지 않았다.
- **Type consistency:** RecommendationPriceSnapshot은 adapter, recorder, repository, performance Policy가 공통으로 사용하며 `(run_id, recommendation_index, snapshot_kind)`가 snapshot identity다.

## 구현 기록

### 2026-08-05 KST — 문서·운영 조립 검증

- `RUN_LIVE_MARKET_DATA_TESTS=1` opt-in은 KIS를 실제 호출하는 계약 테스트에만 적용했다. 기본 pytest는 외부 API를 호출하지 않으며 KIS 자격 증명이 없으면 해당 테스트를 skip한다. production dashboard와 scheduled worker는 KIS 자격 증명이 모두 설정되면 KIS 실시간 가격을 호출하고, 미설정·실패 시 KRX fallback을 사용한다.
- Compose의 dashboard와 `schedule-worker`에 KIS 설정 이름만 전달하고, README·운영 문서·아키텍처·Domain·ADR에 KIS 우선/7일 KRX 종가 fallback, KST 표기, `가격 미확인`, 사후 단순 가격 비교 한계와 Harness-owned persistence 경계를 기록했다.
- 환경 파일의 KIS 변경은 `--force-recreate dashboard schedule-worker`로 반영한다. key·secret·token·authorization header·raw payload는 문서 예시, 로그, DB, SSE, Telegram에 포함하지 않는다.
- 검증은 기본 live-test skip을 포함한 전체 pytest, 임시 pycache compileall, diff check, Compose config 및 PostgreSQL → migration → worker smoke로 수행했다. smoke 종료는 `docker-compose down`만 사용해 named volume을 보존했다.

### 2026-08-10 KST — 통합 전 회귀 안정화

- `CollectPostsRequest.ended_at`을 적용한 IR RSS 수집기가 고정된 fixture 날짜를 실제 현재 시각 기준으로 제외하던 테스트 취약점을 확인했다. 두 RSS fixture request에 명시적 UTC 종료 시각을 지정해 기간 경계를 재현 가능하게 고정했다.
- 추천 성과 기능은 Task 1–5의 커밋과 대응 테스트로 구현되어 있으며, 이 기록은 통합 전 전체 회귀와 문서 상태 정리를 위한 후속 변경이다.
