# 과거 실행 재현 및 재시도 분석 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KST 기준 과거 날짜의 수집·스크리닝 실행을 재현하고, 단계별 재시도 결과를 안전한 감사 데이터로 남긴다.

**Architecture:** 외부 입력인 기준 시각은 `CollectPostsRequest`의 UTC `ended_at`으로 검증해 Provider에 주입한다. Harness가 실행 시각·수집 범위·안전한 단계 관측을 JSONL 및 PostgreSQL에 저장하고, Provider·Parser·Policy·Workflow는 DB를 직접 호출하지 않는다. LangGraph의 기존 transport 재시도는 유지하되, 노드 재시도 시도 횟수도 progress 관측으로 분리한다.

**Tech Stack:** Python 3.11, Pydantic, LangGraph, SQLAlchemy async, Alembic, PostgreSQL, OpenAI Structured Output.

## Global Constraints

- 모든 사용자 입력 날짜는 KST로 받고 내부 저장 시각은 UTC로 저장한다.
- 실제 OpenAI 실행은 사용자가 승인한 최대 25개 입력으로 제한한다.
- 기사 원문, URL query, prompt, API key, 예외 전문은 로그·감사 JSONL에 저장하지 않는다.
- Provider·Normalizer·Parser·Policy·Workflow는 DB를 직접 호출하지 않고 Harness 어댑터만 영속화한다.
- 부분 성공을 유지하며, 재시도 가능 오류가 아닌 오류는 재시도하지 않는다.

---

### Task 1: 기준 시각을 주입할 수 있는 수집 계약

**Files:**
- Modify: `app/models/collect_posts.py`
- Modify: `app/providers/dart.py`
- Modify: `app/cli.py`
- Test: `tests/test_dart_provider.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `CollectPostsRequest(ended_at: datetime | None)`.
- Produces: CLI `--as-of-kst YYYY-MM-DD`가 해당 KST 일자의 종료 시각을 UTC `ended_at`으로 변환한다.

- [ ] **Step 1: 실패하는 기준 시각 Provider 테스트를 작성한다.**

```python
async def test_dart_uses_request_ended_at_for_date_range() -> None:
    request = CollectPostsRequest(..., period=timedelta(hours=24), ended_at=reference)
    await provider.collect(request)
    assert client.queries[0]["bgn_de"] == "20260731"
    assert client.queries[0]["end_de"] == "20260731"
```

- [ ] **Step 2: 해당 테스트가 `ended_at` 미지원으로 실패하는지 실행한다.**

Run: `uv run pytest tests/test_dart_provider.py -q`
Expected: FAIL because `CollectPostsRequest` has no `ended_at` field.

- [ ] **Step 3: 최소 계약과 Provider 주입 구현을 작성한다.**

```python
ended_at: Optional[datetime] = None

def collection_ended_at(request: CollectPostsRequest) -> datetime:
    return request.ended_at or datetime.now(timezone.utc)
```

- [ ] **Step 4: KST CLI 날짜 파싱과 UTC 변환 테스트·구현을 작성한다.**

```python
assert parse_as_of_kst("2026-07-31") == datetime(2026, 8, 1, tzinfo=timezone.utc)
```

- [ ] **Step 5: 관련 테스트를 실행한다.**

Run: `uv run pytest tests/test_dart_provider.py tests/test_cli.py -q`
Expected: PASS.

### Task 2: 안전한 실행·재시도 관측 영속화

**Files:**
- Modify: `app/harness/execution_audit.py`
- Modify: `app/persistence/schema.py`
- Modify: `app/persistence/harness_adapter.py`
- Modify: `app/persistence/database.py`
- Create: `app/persistence/execution_repository.py`
- Create: `alembic/versions/20260805_02_execution_run_observations.py`
- Test: `tests/test_execution_audit.py`
- Test: `tests/test_execution_repository.py`

**Interfaces:**
- Produces: `WorkflowExecutionAudit`의 선택적 `collection_ended_at` 및 `retry_observations`.
- Produces: Harness-owned `ExecutionAuditPersistence.append(audit)`.

- [ ] **Step 1: Postgres 저장 payload에 원문·URL·prompt가 없음을 확인하는 실패 테스트를 작성한다.**

```python
assert stored["collection_ended_at"] == reference
assert "content" not in stored
assert "url" not in stored
```

- [ ] **Step 2: repository가 없어서 실패하는지 실행한다.**

Run: `uv run pytest tests/test_execution_repository.py -q`
Expected: FAIL because the execution repository does not exist.

- [ ] **Step 3: run summary와 retry observation 테이블·repository·Harness adapter를 구현한다.**

```python
execution_runs = Table("execution_runs", metadata, ...)
execution_retry_observations = Table("execution_retry_observations", metadata, ...)
```

- [ ] **Step 4: Alembic migration과 Harness append 경로를 구현한다.**

```python
await execution_persistence.persist(audit)
```

- [ ] **Step 5: 단위·repository 테스트를 실행한다.**

Run: `uv run pytest tests/test_execution_audit.py tests/test_execution_repository.py -q`
Expected: PASS.

### Task 3: LangGraph 재시도 관측과 실패 보고

**Files:**
- Modify: `app/workflows/screening/workflow.py`
- Modify: `app/workflows/screening/result.py`
- Modify: `app/web/app.py`
- Test: `tests/test_workflow_retry.py`
- Test: `tests/test_live_workflow_progress.py`

**Interfaces:**
- Produces: `WorkflowProgressEvent.retry_attempt` 및 `retrying` 안전 관측.
- Produces: stage별 `attempt`, `error_type`만 보존하는 retry event.

- [ ] **Step 1: 노드가 retryable 오류 뒤 성공했을 때 retry progress를 내보내야 한다는 실패 테스트를 작성한다.**

```python
assert progress_events[0].node == "screen"
assert progress_events[0].retry_attempt == 2
```

- [ ] **Step 2: 테스트가 progress 계약 부재로 실패하는지 실행한다.**

Run: `uv run pytest tests/test_workflow_retry.py tests/test_live_workflow_progress.py -q`
Expected: FAIL because retry observations are not emitted.

- [ ] **Step 3: LangGraph task retry stream metadata를 안전한 progress event로 투영한다.**

```python
WorkflowRetryObservation(stage=node, attempt=attempt, error_type=error_type)
```

- [ ] **Step 4: 테스트를 재실행한다.**

Run: `uv run pytest tests/test_workflow_retry.py tests/test_live_workflow_progress.py -q`
Expected: PASS.

### Task 4: 과거 금요일 실행과 운영 보고

**Files:**
- Create: `docs/pr-49-historical-retry-analysis.md`
- Modify: `WORKFLOW.md`
- Modify: `TESTING_GUIDE.md`
- Modify: `DECISION_LOG.md`

**Interfaces:**
- Consumes: `--collect --sources dart,ir_rss --limit 25 --period-hours 24 --as-of-kst YYYY-MM-DD`.
- Produces: 날짜별 실행 ID, 안전한 집계, 실패 유형, 실제 재시도 여부를 담은 한국어 보고서.

- [ ] **Step 1: mock mode 네 날짜 smoke test를 실행한다.**

Run: four CLI calls for 2026-07-10, 17, 24, 31 with `--mode mock --limit 25`.
Expected: each run writes only safe audit data and has no input-size violation.

- [ ] **Step 2: 실제 OpenAI mode를 같은 조건으로 실행한다.**

Run: four approved calls with `--mode openai --limit 25`.
Expected: partial success is retained and failures contain only safe type observations.

- [ ] **Step 3: 결과·실패 원인·재시도 변경 근거를 한국어 문서에 기록한다.**

```markdown
| KST 기준일 | 입력 수 | 최종 상태 | 재시도 | 안전한 실패 유형 |
| --- | ---: | --- | ---: | --- |
```

- [ ] **Step 4: 전체 검증과 migration smoke를 실행한다.**

Run: `uv run pytest && uv run python -m compileall app tests && git diff --check`
Expected: PASS.
