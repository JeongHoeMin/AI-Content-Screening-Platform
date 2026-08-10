# PR-34 — Workflow Execution Audit v1

## 목표

Phase 9의 첫 운영 단위로 Screening Workflow 실행마다 재현·감사에 필요한 안전한 요약 기록을 남긴다. 실행 상태 변경과 persistence는 Harness가 소유하며, Domain·Policy·Workflow 노드는 파일 시스템을 알지 않는다.

## 범위

- immutable Pydantic execution audit record와 성공/실패 상태 계약을 추가한다.
- `ScreeningWorkflow` 실행을 감싸는 Harness가 시작·종료 시각, execution ID, mode, 입력 기사 수, workflow statistics 또는 제한된 오류 유형을 기록한다.
- JSON Lines 파일 sink는 명시적으로 주입됐을 때만 append한다.
- CLI에 opt-in `--audit-log`를 추가해 기존 JSON stdout schema를 바꾸지 않는다.
- 성공·실패 record, sink 호출 순서, JSONL 표현, CLI opt-in 회귀를 테스트한다.

## 비범위

- scheduler, alert delivery, retry orchestration, database/object storage, retention purge, distributed locking, OpenTelemetry exporter, 비용·latency alert policy는 후속 작업이다.
- 기사 원문, prompt, API key, 개인정보, raw SDK response, recommendation/impact 전체 snapshot은 audit log에 저장하지 않는다.
- Workflow·Policy의 판단 규칙과 CLI success JSON schema는 변경하지 않는다.

## 설계 결정

1. audit record는 `execution_id`, UTC timestamps, duration, execution mode, input count, aggregate `WorkflowStatistics`, bounded `error_type`만 가진다. 실패 record는 statistics를 포함하지 않고 성공 record는 error type을 포함하지 않는다.
2. audit persistence는 `ScreeningExecutionHarness`가 소유한다. Workflow는 무상태·side-effect-free public `run()` 계약을 유지한다.
3. file sink는 한 record를 한 JSON line으로 append한다. 명시적 audit sink의 쓰기 실패는 운영 기록을 보장할 수 없으므로 실행 실패로 전파한다.
4. CLI는 `--audit-log`가 없으면 sink를 조립하지 않아 기존 동작을 유지한다. 로그 자체가 stdout JSON을 오염시키지 않는다.

## 구현 순서

1. execution audit Domain, sink interface, file sink, workflow Harness를 추가한다.
2. Bootstrap/CLI에서 opt-in sink를 조립한다.
3. 단위·CLI 회귀, 전체 test suite, compileall, diff check를 실행한다.

## 변경 이력

- 2026-07-30: 최초 계획 작성. Phase 9의 persistence 기반을 안전한 실행 요약 audit trail로 제한했다.
