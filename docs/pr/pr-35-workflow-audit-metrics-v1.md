# PR-35 — Workflow Audit Metrics v1

## 목표

PR-34의 안전한 terminal execution audit records를 집계해 운영자가 workflow 성공률, 처리량, latency와 screening outcome 분포를 확인할 수 있게 한다. 집계는 Harness/operations 경계에서만 수행하며 Workflow, Domain Policy, LLM에는 새 책임을 추가하지 않는다.

## 범위

- immutable Pydantic metric snapshot과 deterministic calculator를 추가한다.
- JSONL audit reader가 각 행을 `WorkflowExecutionAudit`으로 검증하고, malformed record를 안전한 file/line 위치 오류로 보고한다.
- CLI에 audit-only report mode를 추가한다. report mode는 workflow를 실행하거나 OpenAI config를 읽지 않는다.
- 전체 실행, 성공/실패, duration, input article count, 성공 execution의 screening statistics를 합계로 제공한다.
- 빈 audit log, success/failure 혼합, malformed JSON/contract, CLI JSON projection을 테스트한다.

## 비범위

- metrics exporter, dashboard, alert delivery/threshold policy, database query, windowed time-series storage, retention purge, scheduler는 후속 작업이다.
- audit record가 보존하지 않는 기사 본문, prompt, recommendation/impact snapshot, raw 오류 문자열은 metrics 입력·출력에 포함하지 않는다.

## 설계 결정

1. metrics는 audit record의 arithmetic projection이며 accept/review/reject 같은 제품 결정을 다시 계산하거나 바꾸지 않는다.
2. `WorkflowStatistics`는 성공 record에만 존재하므로 outcome 합계도 성공 execution에서만 계산한다. 실패는 별도 count·duration으로 보존한다.
3. reader는 한 행이라도 malformed이면 조용히 누락시키지 않고 입력 오류로 실패한다. 감사 데이터의 완전성은 부분 성공보다 중요하다.
4. report mode는 `--audit-report PATH`만 사용하며 기존 `--input` workflow 실행 mode와 mutually exclusive다. stdout에는 JSON report만 기록한다.

## 구현 순서

1. audit reader, metric models, deterministic calculator를 추가한다.
2. CLI parser와 report serializer를 추가한다.
3. unit/CLI regression, 전체 suite, compileall, diff check를 수행한다.

## 변경 이력

- 2026-07-30: 최초 계획 작성. PR-34 audit trail을 source of truth로 사용하며, alerting/scheduler는 본 단위에서 제외한다.
