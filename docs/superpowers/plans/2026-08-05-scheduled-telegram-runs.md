# KST 예약 실행·Telegram 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PostgreSQL에 저장한 한국시간 cron 설정대로 Docker worker가 추천을 실행하고, 실행 완료 뒤 안전한 한국어 Telegram 요약을 보낸다.

**Architecture:** `app/harness/`가 due job 조회·lease·실행 결과 영속화·Telegram 사후 전송을 소유한다. `app/persistence/`는 schedule/lease/execution repository만 제공하고, Workflow·Provider·Parser·Policy는 DB와 Telegram을 모른다. 설정 페이지는 FastAPI의 Harness API를 통해 validated schedule만 생성·수정한다.

**Tech Stack:** Python 3.9, Pydantic, FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Docker Compose, Telegram Bot HTTP API, pytest

## Global Constraints

- UI, 운영 문서, Telegram 문구와 KST 사용 문구는 한국어로 작성한다.
- DB timestamp는 UTC, cron 해석·설정 UI·Telegram 예약 시각은 `Asia/Seoul`로 처리한다.
- Telegram token/chat ID는 환경변수로만 읽고 DB, API response, 로그, JSONL에 저장하지 않는다.
- Telegram 실패는 durable execution을 실패로 바꾸지 않으며 safe error type만 structlog에 남긴다.
- Worker만 schedule lease, execution record, Telegram delivery의 side effect를 수행한다.
- 추천 시점 가격·평가손익은 다음 별도 `recommendation-performance` PR에서 구현한다.

---

### Task 1: 스케줄 Domain·DB schema·repository를 추가한다

**Files:**
- Create: `app/models/scheduled_recommendation.py`
- Create: `app/persistence/schedule_repository.py`
- Create: `alembic/versions/20260805_03_scheduled_recommendation_jobs.py`
- Modify: `app/persistence/schema.py`, `app/persistence/harness_adapter.py`, `app/persistence/database.py`, `app/persistence/__init__.py`
- Test: `tests/test_scheduled_recommendation.py`, `tests/test_persistence_migration.py`

**Interfaces:**
- Produces immutable `ScheduledRecommendationJob` (`id`, `active`, `cron_expression`, `timezone`, collection filter, limit, `telegram_enabled`, `version`, UTC next/last execution fields).
- Produces `ScheduledRecommendationRepository.claim_due(now_utc, lease_owner, lease_until)` that atomically leases one due active job and advances its next KST cron time.

- [ ] **Step 1: 실패 테스트를 작성한다**

```python
def test_schedule_rejects_non_kst_or_invalid_five_field_cron() -> None:
    with pytest.raises(ValidationError):
        ScheduledRecommendationJob(cron_expression="bad", timezone="UTC")

def test_claim_due_returns_only_one_versioned_lease() -> None:
    assert claimed_job.lease_owner == "worker-1"
```

- [ ] **Step 2: 대상 테스트가 Domain/repository 부재로 실패함을 확인한다**

Run: `pytest tests/test_scheduled_recommendation.py -v`

- [ ] **Step 3: 최소 구현을 작성한다**

`croniter`를 새 의존성으로 추가하지 않고 기존 5필드 cron 범위(`*`, 숫자, 쉼표, 범위, step)를 Pydantic validator와 작은 deterministic next-run calculator로 지원한다. migration은 `scheduled_recommendation_jobs`, `scheduled_recommendation_executions`와 lease/version 제약만 만든다.

- [x] **Step 4: repository와 migration 테스트를 통과시킨다**

### Task 2: Harness worker와 안전한 Telegram adapter를 추가한다

**Files:**
- Create: `app/harness/scheduled_recommendations.py`
- Create: `app/harness/telegram.py`
- Create: `app/config/telegram.py`
- Modify: `app/harness/__init__.py`, `app/config/__init__.py`, `app/persistence/harness_adapter.py`
- Test: `tests/test_scheduled_recommendation.py`, `tests/test_telegram_delivery.py`

**Interfaces:**
- `ScheduledRecommendationWorker.run_due(now_utc) -> int`는 leased job마다 injected run function을 정확히 한 번 호출한다.
- `TelegramRecommendationReporter.deliver(summary)`는 token/chat ID가 유효한 경우에만 Telegram API adapter를 호출한다.

- [ ] **Step 1: 실패 테스트를 작성한다**

```python
async def test_worker_persists_terminal_execution_before_best_effort_telegram() -> None:
    assert recorder.events == ["execution_persisted", "telegram_attempted"]

async def test_telegram_failure_preserves_succeeded_execution() -> None:
    assert execution.status is ScheduledExecutionStatus.SUCCEEDED
```

- [ ] **Step 2: 테스트가 worker/adapter 부재로 실패함을 확인한다**

- [ ] **Step 3: 최소 구현을 작성한다**

Telegram message는 KST 예약 시각, 테마/주제, 완료 상태, 안전한 count, BUY/SELL 회사명·ticker·score·reason code, 실행 ID만 담는다. 원문, prompt, exception text, token은 포함하지 않는다.

- [ ] **Step 4: partial-success·lease·delivery-failure 테스트를 통과시킨다**

### Task 3: 설정 API·페이지와 Docker worker를 조립한다

**Files:**
- Create: `app/worker.py`
- Modify: `app/web/app.py`, `app/web/dashboard_html.py`, `app/config/persistence.py`, `docker-compose.yml`, `Dockerfile`
- Test: `tests/test_web_schedule_settings.py`, `tests/test_docker_compose_database.py`

**Interfaces:**
- `GET/PUT /api/settings/scheduled-recommendation`은 secret 없는 schedule model만 반환·저장한다.
- `app.worker`는 configured PostgreSQL이 없으면 fail-fast하고, KST due job poll loop를 실행한다.

- [ ] **Step 1: 실패 테스트를 작성한다**

```python
def test_schedule_settings_api_rejects_stale_version() -> None:
    assert client.put(url, json=stale_payload).status_code == 409

def test_dashboard_exposes_kst_schedule_setting_controls() -> None:
    assert "예약 실행 설정" in response.text
```

- [ ] **Step 2: API/UI/Docker tests가 실패함을 확인한다**

- [ ] **Step 3: 최소 구현을 작성한다**

대시보드는 하나의 활성 일일/cron schedule 편집, 테마·주제·25/50/100 limit, Telegram enable toggle, 마지막/다음 KST 실행 시각을 제공한다. Compose는 dashboard와 같은 environment를 받는 `worker` service를 추가하고 PostgreSQL healthcheck 이후 실행한다.

- [ ] **Step 4: FastAPI·Compose 조립 테스트를 통과시킨다**

### Task 4: 운영 문서·검증·리뷰를 수행한다

**Files:**
- Create: `docs/운영-예약실행-텔레그램.md`
- Modify: `PROJECT_GUIDE.md`, `ARCHITECTURE.md`, `WORKFLOW.md`, `ROADMAP.md`, `DECISION_LOG.md`, `README.md`, `docs/superpowers/plans/2026-08-05-scheduled-telegram-runs.md`
- Test: 전체 pytest 및 Docker Compose migration smoke test

- [ ] **Step 1: 한국어 운영 문서를 작성한다**

문서는 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `DATABASE_URL`, `IR_RSS_FEEDS`, KST cron 예시, worker start, secret 보관, 장애 확인·재실행 절차를 명시한다.

- [ ] **Step 2: 전체 검증을 실행한다**

Run: `uv run pytest`

Run: `uv run python -m compileall app tests`

Run: `git diff --check`

Run: `docker compose --env-file /secure/screening.env up --build -d` 및 migration/health smoke test

- [ ] **Step 3: 코드 리뷰에서 나온 Critical/Important를 반영하고 재검증한다**

- [ ] **Step 4: 커밋·PR·리뷰 반영·병합을 수행한다**

## 자체 점검

- 실제 시스템 crontab을 수정하지 않고 DB schedule와 Docker worker만 사용한다.
- 가격 snapshot/현재 수익률은 이 PR에 넣지 않아 별도 performance PR의 경계를 유지한다.
- schedule lease와 optimistic version이 worker 재시작·중복 실행을 막는지 테스트한다.
- Telegram은 성공한 durable execution 뒤의 best-effort 부수 효과인지 검증한다.

## 구현 기록

### 2026-08-05 KST — worker·설정 페이지 조립

- `ScheduledRecommendationJob`의 KST 5필드 cron, PostgreSQL lease, terminal execution record와 Alembic `20260805_03`을 구현했다.
- `schedule-worker`는 RSS 기반 기존 recommendation Harness를 재사용하며 Telegram은 terminal DB 기록 뒤에만 best-effort로 호출한다.
- Compose에 `db-migrate` 일회성 서비스를 추가해 dashboard·worker가 migration 성공 이후에만 시작하도록 수정했다. 이전에는 worker가 테이블 생성 전 시작해 `UndefinedTableError`로 종료되는 것을 Docker smoke에서 확인했다.
- `/settings`는 `.env`의 `SCHEDULE_SETTINGS_PASSWORD`를 확인한 뒤 HttpOnly session cookie를 발급하며, cron·테마·주제·건수·Telegram 사용 여부만 저장한다. Telegram token/chat ID는 페이지나 DB에 노출하지 않는다.
- 설정 저장은 version을 함께 전송하고 PostgreSQL update predicate로 optimistic concurrency를 강제한다. 다른 브라우저가 먼저 저장한 경우 UI는 409을 안내하고 stale 값을 덮어쓰지 않는다.
- 코드 리뷰에서 발견한 중복 `get()` 정의를 제거했고, scheduled run은 terminal 뒤 dashboard memory state를 즉시 제거한다. 이미 존재하는 실행 slot은 재실행하지 않고 `lease_expired` terminal 관측만 남긴 뒤 다음 slot으로 이동한다.
- lease는 5분 heartbeat로 갱신한다. terminal transition은 현재 lease owner와 `running` execution을 row lock으로 확인한 경우에만 상태를 바꾸고 lease를 해제한다. 이 전이가 실패하면 Telegram도 보내지 않는다.
- 검증: `pytest -q` 536 passed, `compileall app tests`, `git diff --check`, Compose config, PostgreSQL → `db-migrate` → `schedule-worker` smoke와 Alembic revision `20260805_03`을 확인했다.
