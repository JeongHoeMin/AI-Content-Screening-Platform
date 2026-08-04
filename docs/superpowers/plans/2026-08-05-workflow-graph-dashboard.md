# 워크플로우 그래프 대시보드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대시보드에서 실제 수집·LangGraph 처리 순서와 재시도 정책을 연결 그래프로 표시하고 실행 이벤트가 해당 그래프를 안전하게 갱신하게 한다.

**Architecture:** `DashboardRunManager`는 Harness-owned SSE 투영만 수행하고, Workflow는 기존의 노드 완료 관측 계약을 유지한다. 브라우저는 서버가 전달한 `active_stage`, `completed_stage_count`, terminal failure의 단계·시도 횟수만 사용해 실제 그래프 노드와 재시도 경로를 상태화하며, LLM 원문·오류 전문은 표시하거나 저장하지 않는다.

**Tech Stack:** Python 3.9, FastAPI SSE, Pydantic, LangGraph, 정적 HTML/CSS/JavaScript, pytest

## Global Constraints

- 모든 사용자 문구와 이번 설계·목표 문서는 한국어로 작성한다.
- Provider·Normalizer·Parser·Policy·Workflow는 DB를 직접 호출하지 않으며, 대시보드는 Harness-owned 실행 투영만 담당한다.
- 재시도는 기존 `extract`·`deduplicate`·`screen`·`cross_validate`의 제한된 LLM transport/authentication 오류에만 적용되는 총 3회(최초 실행 뒤 5초·10초) 정책을 표시한다.
- 기사 원문, prompt, API key, raw SDK 응답, 예외 전문을 그래프·SSE·로그에 노출하지 않는다.
- 모든 Python 함수·변수·반환값에 type hint를 쓰고, 로그에는 structlog만 사용한다.

---

### Task 1: 실제 노드 순서와 안전한 실패 상태를 대시보드 계약에 맞춘다

**Files:**
- Modify: `app/web/app.py`
- Test: `tests/test_web_dashboard.py`

**Interfaces:**
- Consumes: `WorkflowProgressEvent.node`, `WorkflowStageRetriesExhaustedError.stage`, `error_type`, `attempts`
- Produces: `DashboardRunManager._WORKFLOW_NODES`에 `deduplicate`를 포함한 실제 순서와 `DashboardEvent`의 safe terminal failure projection

- [x] **Step 1: 실패 테스트를 작성한다**

```python
def test_dashboard_workflow_order_includes_deduplicate_before_screen() -> None:
    assert DashboardRunManager._next_workflow_stage("extract") == "deduplicate"
    assert DashboardRunManager._next_workflow_stage("deduplicate") == "screen"
```

- [x] **Step 2: 테스트가 현재 `extract -> screen`으로 실패함을 확인한다**

Run: `UV_CACHE_DIR=/private/tmp/ai-screening-uv-cache uv run pytest tests/test_web_dashboard.py::test_dashboard_workflow_order_includes_deduplicate_before_screen -v`

- [x] **Step 3: 최소 구현을 작성한다**

```python
_WORKFLOW_NODES: tuple[str, ...] = (
    "evaluate", "extract", "deduplicate", "screen", "cross_validate",
    "resolve", "analyze", "aggregate", "score", "recommend", "select_candidates",
)
```

- [x] **Step 4: 대상 테스트를 다시 실행해 통과를 확인한다**

- [x] **Step 5: 커밋은 최종 Task 뒤에 한 번만 수행한다**

### Task 2: 정적 클라이언트를 실제 그래프와 재시도 경로로 바꾼다

**Files:**
- Modify: `app/web/dashboard_html.py`
- Test: `tests/test_web_dashboard.py`

**Interfaces:**
- Consumes: SSE `active_stage`, `completed_stage_count`, `failure_stage`, `failure_attempts`, `error_type`
- Produces: `#workflow-graph`, 노드 ID `graph-<stage>`, retry edge `#retry-path`, `renderWorkflowGraph()`

- [x] **Step 1: 실패 테스트를 작성한다**

```python
def test_dashboard_page_exposes_actual_workflow_graph_and_retry_path() -> None:
    response = TestClient(create_web_app()).get("/")
    assert 'id="workflow-graph"' in response.text
    assert 'id="graph-deduplicate"' in response.text
    assert 'id="retry-path"' in response.text
    assert "renderWorkflowGraph" in response.text
    assert "failure_attempts" in response.text
```

- [x] **Step 2: 테스트가 그래프 요소 부재로 실패함을 확인한다**

Run: `UV_CACHE_DIR=/private/tmp/ai-screening-uv-cache uv run pytest tests/test_web_dashboard.py::test_dashboard_page_exposes_actual_workflow_graph_and_retry_path -v`

- [x] **Step 3: 최소 구현을 작성한다**

```javascript
const workflowNodes=["collect","directory","evaluate","extract","deduplicate","screen","cross_validate","resolve","analyze","aggregate","score","recommend","select_candidates"];
const renderWorkflowGraph=()=>{/* completed는 녹색, active는 파랑, terminal failure는 빨강으로 표시 */};
const setRetryState=data=>{/* failure_stage와 failure_attempts가 있을 때만 고정 재시도 경로를 표시 */};
```

그래프는 CSS Grid 기반으로 13개 실제 단계와 각 단계의 순차 화살표를 렌더링한다. `extract`·`deduplicate`·`screen`·`cross_validate`에서만 `재시도: 최초 실행 뒤 5초·10초 간격, 최대 3회` 보조 경로를 보이며, terminal failure가 도착했을 때에만 실패 단계·안전한 error type·실제 최종 시도 횟수를 표시한다.

- [x] **Step 4: 대상 테스트를 다시 실행해 통과를 확인한다**

- [x] **Step 5: 브라우저 렌더링 단언을 기존 페이지 회귀 테스트에 추가한다**

### Task 3: 운영 문서와 변경 이력을 갱신하고 전체 회귀를 검증한다

**Files:**
- Modify: `WORKFLOW.md`
- Modify: `ARCHITECTURE.md`
- Modify: `DECISION_LOG.md`
- Modify: `docs/superpowers/plans/2026-08-05-workflow-graph-dashboard.md`
- Test: `tests/test_web_dashboard.py`, `tests/test_live_workflow_progress.py`

**Interfaces:**
- Consumes: 기존 LangGraph retry boundary 및 Dashboard SSE projection
- Produces: 재시도 관측 범위(terminal attempts only)와 그래프 상태 표시의 명시된 한계

- [x] **Step 1: 문서에 새로운 그래프와 재시도 관측 범위를 한국어로 기록한다**

`WORKFLOW.md`에는 `extract → deduplicate → screen` 순서를, `ARCHITECTURE.md`에는 대시보드가 workflow를 제어하지 않는 SSE consumer임을, `DECISION_LOG.md`에는 재시도 시도 중간 관측을 아직 만들지 않고 terminal attempt만 안전하게 표시하는 결정을 ADR로 남긴다.

- [x] **Step 2: 관련 대시보드·진행 이벤트 테스트를 실행한다**

Run: `UV_CACHE_DIR=/private/tmp/ai-screening-uv-cache uv run pytest tests/test_web_dashboard.py tests/test_live_workflow_progress.py -q`

- [x] **Step 3: 전체 테스트와 정적 검증을 실행한다**

Run: `UV_CACHE_DIR=/private/tmp/ai-screening-uv-cache uv run pytest`

Run: `UV_CACHE_DIR=/private/tmp/ai-screening-uv-cache uv run python -m compileall app tests`

Run: `git diff --check`

- [ ] **Step 4: 변경을 검토하고 커밋한다**

```bash
git add app/web/app.py app/web/dashboard_html.py tests/test_web_dashboard.py WORKFLOW.md ARCHITECTURE.md DECISION_LOG.md docs/superpowers/plans/2026-08-05-workflow-graph-dashboard.md
git commit -m "feat: 워크플로우 그래프와 재시도 상태 표시"
```

## 자체 점검

- 실제 graph에는 `deduplicate`가 있으며 대시보드 순서도 동일하게 반영한다.
- 재시도 중간 시도를 실제로 수집하지 않는 현재 LangGraph 계약을 과장하지 않고, 최종 실패의 실제 `attempts`만 표시한다.
- 그래프에 표시되는 모든 오류 정보는 stage, bounded error type, attempt count뿐이다.
- RSS 미설정 문제와 실제 API 과거 실행은 별도 입력 설정 과제로 유지하며, UI 변경 범위에 섞지 않는다.
