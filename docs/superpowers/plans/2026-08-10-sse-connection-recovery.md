# SSE Connection Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the dashboard aligned with a recommendation run's actual terminal outcome after an SSE interruption, while recording bounded lifecycle diagnostics.

**Architecture:** FastAPI logs lifecycle-only events around the unchanged SSE payload. The React hook uses a bounded policy to reopen SSE and query `GET /api/runs/{run_id}`, the authority for terminal result.

**Tech Stack:** FastAPI, structlog, React 19, TypeScript, Vitest, pytest.

## Global Constraints

- Do not change the SSE `DashboardEvent` payload or normal result API schema.
- Logs contain only run ID, bounded lifecycle/recovery values, and terminal type.
- A `409` result response means the background execution is still running.
- In-memory runs cannot recover across a dashboard container restart.

---

### Task 1: Backend SSE lifecycle diagnostics

**Files:**
- Modify: `app/web/app.py:1249-1266`
- Test: `tests/test_web_dashboard.py`

**Interfaces:**
- Consumes: `DashboardRunManager.events(run_id)`.
- Produces: `dashboard_sse_stream_opened`, `dashboard_sse_terminal_sent`, and `dashboard_sse_stream_closed` logs with only safe lifecycle fields.

- [ ] **Step 1: Write the failing lifecycle test**

```python
def test_event_stream_logs_safe_lifecycle_events(caplog):
    client = TestClient(create_web_app(_SingleEventManager()))
    with client.stream("GET", "/api/runs/run-1/events") as response:
        assert response.status_code == 200
        list(response.iter_text())
    assert "dashboard_sse_stream_opened" in [record.getMessage() for record in caplog.records]
```

- [ ] **Step 2: Verify RED**

Run: `UV_CACHE_DIR=/private/tmp/ai-screening-uv-cache uv run pytest tests/test_web_dashboard.py -k sse_lifecycle -q`

Expected: FAIL because lifecycle logging is absent.

- [ ] **Step 3: Implement bounded lifecycle logs**

```python
logger.info("dashboard_sse_stream_opened", run_id=run_id, lifecycle="opened")
try:
    async for event in run_manager.events(run_id):
        if event.type in {"completed", "failed"}:
            logger.info("dashboard_sse_terminal_sent", run_id=run_id, lifecycle="terminal", terminal_type=event.type)
        yield payload
finally:
    logger.info("dashboard_sse_stream_closed", run_id=run_id, lifecycle="closed", terminal_type=terminal_type)
```

- [ ] **Step 4: Verify GREEN**

Run: `UV_CACHE_DIR=/private/tmp/ai-screening-uv-cache uv run pytest tests/test_web_dashboard.py -k sse_lifecycle -q`

Expected: PASS.

### Task 2: Pure frontend recovery policy

**Files:**
- Create: `frontend/src/lib/sseRecovery.ts`
- Create: `frontend/src/lib/sseRecovery.test.ts`

**Interfaces:**
- Produces: `nextSseRecoveryDelay(attempt: number): number | null` and `classifySseResultStatus(status: number): "completed" | "running" | "failed"`.

- [ ] **Step 1: Write failing tests**

```ts
expect(nextSseRecoveryDelay(0)).toBe(1000);
expect(nextSseRecoveryDelay(1)).toBe(3000);
expect(nextSseRecoveryDelay(2)).toBeNull();
expect(classifySseResultStatus(409)).toBe("running");
```

- [ ] **Step 2: Verify RED**

Run: `npm test -- --run src/lib/sseRecovery.test.ts`

Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement the pure policy**

```ts
const RECOVERY_DELAYS_MS = [1000, 3000] as const;
export const nextSseRecoveryDelay = (attempt: number) => RECOVERY_DELAYS_MS[attempt] ?? null;
export const classifySseResultStatus = (status: number) => status === 200 ? "completed" : status === 409 ? "running" : "failed";
```

- [ ] **Step 4: Verify GREEN**

Run: `npm test -- --run src/lib/sseRecovery.test.ts`

Expected: PASS.

### Task 3: Hook recovery after SSE error

**Files:**
- Modify: `frontend/src/lib/useRecommendationRun.ts:116-248`
- Create: `frontend/src/lib/useRecommendationRun.test.ts`

**Interfaces:**
- Consumes: Task 2 helpers and the existing events/result endpoints.
- Produces: completed result after a recoverable disconnect; failure only after actual server failure or exhausted bounded recovery.

- [ ] **Step 1: Write a failing controlled-EventSource test**

```ts
it("loads a completed result after EventSource errors", async () => {
  eventSource.emitError();
  await flushRecoveryTimer();
  expect(fetch).toHaveBeenCalledWith(`/api/runs/${runId}`);
  expect(state.progress.status).toBe("completed");
});
```

- [ ] **Step 2: Verify RED**

Run: `npm test -- --run src/lib/useRecommendationRun.test.ts`

Expected: FAIL because current `onerror` immediately fails the run.

- [ ] **Step 3: Implement a per-run recovery coordinator**

Keep EventSource, retry count, terminal guard, and timer in refs. On error, query the result endpoint; load a `200` result, retry after `409`, reopen SSE using the helper delay, and fail only after the retry budget. Cancel stale sources and timers on unmount or a new run.

- [ ] **Step 4: Verify GREEN**

Run: `npm test -- --run src/lib/sseRecovery.test.ts src/lib/useRecommendationRun.test.ts`

Expected: PASS for completed recovery, still-running retry, explicit failed event, and cleanup.

### Task 4: Documentation and deployment verification

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `tasks/20260810-1659-sse-connection-diagnostics/task.yaml`

- [ ] **Step 1: Document the boundary**

State that SSE is best-effort progress transport, the result endpoint determines terminal outcome, and diagnostics are bounded metadata only.

- [ ] **Step 2: Verify backend and frontend**

Run the focused backend test, frontend tests, `npm run lint`, `uv run python -m compileall app tests -q`, and `git diff --check`.

- [ ] **Step 3: Rebuild Docker services**

Run: `docker-compose up -d --build --force-recreate dashboard frontend && docker-compose ps dashboard frontend`

Expected: both services are healthy without printing secret values.

## Plan self-review

- Tasks 1–3 cover server diagnostics, bounded recovery policy, and browser recovery.
- Task 4 covers the architecture contract and Docker verification.
- Helper names, outcome values, files, commands, and recovery delays are explicit and consistent.
