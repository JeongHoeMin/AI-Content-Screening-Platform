# PR-38 — Audit Retention & Recovery v1

## 목표

JSONL audit/alert logs를 현재 실행 파일과 immutable archive로 안전하게 분리하고, retention 삭제 대상은 실행 전에 검토 가능한 plan으로 생성한다. 손상 또는 보존 정책 오류가 기록을 조용히 삭제·덮어쓰지 않도록 한다.

## 범위

- immutable `JsonLinesRetentionPolicy`, rotation result, prune plan을 추가한다.
- active JSONL 파일은 timestamped archive로 atomic rename하고 빈 새 active file을 만든다.
- retention policy는 archive 수를 기준으로 prune candidate만 계산하고 파일을 삭제하지 않는다.
- archive name/ownership/empty active log/충돌을 검증하고, retention plan과 rotation을 테스트한다.
- 운영 문서에 recovery, verify, explicit deletion 절차를 기록한다.

## 비범위

- 자동·재귀 삭제, object storage lifecycle, encryption/key rotation, compression, multi-process lock, database retention, malformed audit record repair, CLI maintenance command은 후속 작업이다.
- retention은 Workflow/Policy/LLM 판단과 audit record content를 변경하지 않는다.

## 설계 결정

1. rotation은 `path → path.<UTC timestamp>.archive.jsonl` rename 후 새 active file을 exclusive create한다. archive path가 존재하면 overwrite하지 않고 실패한다.
2. prune plan은 project-created archive naming pattern만 대상이며 active file과 임의 sibling 파일을 포함하지 않는다.
3. v1은 deletion executor를 제공하지 않는다. 운영자는 plan을 검토하고 플랫폼의 recoverable storage/lifecycle 정책으로 삭제를 수행한다.
4. rotation은 empty active log도 archive로 만들지 않고 성공 no-op로 반환한다.

## 운영 절차

1. audit report가 정상인지 확인한다.
2. `rotate()`로 active file을 archive로 분리하고 새 active file을 만든다.
3. `plan_prune()` 결과의 absolute paths와 archive 수를 검토한다.
4. 백업/lifecycle policy가 있는 운영 환경에서만 승인된 candidate를 삭제한다.
5. archive를 `JsonLinesWorkflowExecutionAuditReader`로 읽어 복구 가능성을 검증한다.

## 변경 이력

- 2026-07-30: 최초 계획 작성. 자동 삭제는 사용자 데이터 손실 위험 때문에 v1 범위에서 제외했다.
