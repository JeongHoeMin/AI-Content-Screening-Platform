# Task YAML Schema Guide

이 문서는 각 작업 디렉토리에 생성되는 `task.yaml`의 필드 의미와 작성 규칙을 정의한다.

`task.yaml`은 Agent(Claude Code, Codex 등)가 수행하는 작업의 요구사항, 범위, 진행 상태, 검증 결과를 기록하기 위한 작업 상태 파일이다.

모든 작업은 프로젝트 루트의 `AGENTS.md` 규칙을 따르며, `task.yaml`은 `.agent/templates/task.yaml`을 기준으로 생성한다.

---

## 1. 파일 위치

각 작업은 다음 형식의 디렉토리를 사용한다.

```text
tasks/YYYYMMDD-HHMM-작업이름/
```

각 작업 디렉토리 안에는 반드시 다음 파일이 존재해야 한다.

```text
tasks/<작업 ID>/task.yaml
```

예시:

```text
tasks/20260810-1530-fix-scoring-bug/task.yaml
```

`task.yaml`의 `id` 값은 작업 디렉토리 이름과 동일해야 한다.

---

## 2. 전체 구조

```yaml
schemaVersion: 1

id: ""
title: ""
description: ""

status: planning

createdAt: ""
updatedAt: ""

agent:
  provider: ""
  model: null
  sessionId: null

request:
  summary: ""
  originalPrompt: ""

scope:
  allowedPaths: []
  deniedPaths: []

requirements:
  items: []

plan:
  steps: []

result:
  summary: null
  changedFiles: []
  verifications: []
  completedAt: null

blocker:
  reason: null
  requiredAction: null

history: []
```

---

## 3. 기본 정보

### 3.1 `schemaVersion`

```yaml
schemaVersion: 1
```

`task.yaml` 구조의 버전을 나타낸다.

현재 버전은 `1`이다.

필드 구조가 변경되어 기존 `task.yaml`과 호환되지 않는 경우에만 버전을 증가시킨다.

허용 값:

```text
1
```

---

### 3.2 `id`

```yaml
id: "20260810-1530-fix-scoring-bug"
```

작업의 고유 식별자다.

작업 디렉토리 이름과 동일해야 한다.

형식:

```text
YYYYMMDD-HHMM-작업이름
```

작성 규칙:

- 날짜와 시간은 작업 생성 시점을 사용한다.
- 작업 이름은 영문 소문자와 하이픈을 사용한다.
- 공백은 사용하지 않는다.
- 같은 프로젝트 안에서 중복되지 않아야 한다.

좋은 예시:

```yaml
id: "20260810-1530-fix-scoring-bug"
```

좋지 않은 예시:

```yaml
id: "점수 계산 오류 수정"
id: "fix scoring bug"
id: "task-1"
```

---

### 3.3 `title`

```yaml
title: "Stock Scoring 결과 반올림 오류 수정"
```

사람이 읽기 쉬운 작업 제목이다.

작업의 목적을 짧고 구체적으로 작성한다.

좋은 예시:

```yaml
title: "Stock Scoring 결과 반올림 오류 수정"
```

좋지 않은 예시:

```yaml
title: "수정"
title: "작업"
title: "버그 처리"
```

---

### 3.4 `description`

```yaml
description: "ScoringResult의 contribution 합산 시 소수점 반올림이 Policy 기대값과 어긋나는 문제를 수정한다."
```

작업의 배경과 변경 목적을 설명한다.

가능하면 다음 내용을 포함한다.

- 무엇이 문제인지
- 무엇을 변경할지
- 작업 결과가 어떻게 달라져야 하는지

---

## 4. 작업 상태

### 4.1 `status`

```yaml
status: planning
```

현재 작업 진행 상태를 나타낸다.

허용 값:

```text
planning
in_progress
testing
completed
blocked
cancelled
```

각 상태의 의미:

| 상태 | 의미 |
|---|---|
| `planning` | 요구사항, 영향 범위, 작업 계획을 정리하는 중 |
| `in_progress` | 실제 파일을 생성, 수정 또는 삭제하는 중 |
| `testing` | 테스트, 빌드, 린트, 변경 내용 검증을 수행하는 중 |
| `completed` | 구현과 검증이 모두 성공적으로 완료됨 |
| `blocked` | 외부 문제나 정보 부족으로 진행할 수 없음 |
| `cancelled` | 작업이 취소됨 |

일반적인 상태 전이:

```text
planning
→ in_progress
→ testing
→ completed
```

검증 실패 시:

```text
testing
→ in_progress
→ testing
```

작업 진행이 불가능한 경우:

```text
planning → blocked
in_progress → blocked
testing → blocked
```

작업이 취소된 경우:

```text
planning → cancelled
in_progress → cancelled
blocked → cancelled
```

주의사항:

- `planning` 상태에서 애플리케이션 파일을 수정하지 않는다.
- 파일을 수정하기 전에 `in_progress`로 변경한다.
- 검증을 시작하기 전에 `testing`으로 변경한다.
- 검증에 성공한 경우에만 `completed`로 변경한다.
- 검증 없이 `completed`로 변경하지 않는다.

---

## 5. 시간 정보

### 5.1 `createdAt`

```yaml
createdAt: "2026-08-10T15:30:00+09:00"
```

작업이 생성된 시각이다. 작업 생성 후 변경하지 않는다. ISO 8601 형식을 사용한다.

### 5.2 `updatedAt`

```yaml
updatedAt: "2026-08-10T15:45:00+09:00"
```

`task.yaml`이 마지막으로 갱신된 시각이다.

다음 내용이 변경될 때 함께 갱신한다.

- 작업 상태
- 작업 범위
- 요구사항
- 작업 계획
- 검증 결과
- 차단 정보
- 작업 이력

---

## 6. Agent 정보

### 6.1 `agent.provider`

```yaml
agent:
  provider: "claude-code"
```

작업을 수행하는 Agent 도구를 기록한다.

권장 값:

```text
claude-code
codex
```

### 6.2 `agent.model`

```yaml
agent:
  model: null
```

사용한 모델명을 기록한다. 모델명을 확실히 알 수 있는 경우에만 작성하고, 알 수 없으면 추측하지 않고 `null`로 둔다.

### 6.3 `agent.sessionId`

```yaml
agent:
  sessionId: null
```

Agent 실행 세션 식별자를 기록한다. 확인할 수 있을 때만 작성하고, 확인할 수 없으면 `null`로 둔다.

---

## 7. 사용자 요청

### 7.1 `request.summary`

```yaml
request:
  summary: "Stock Scoring 결과의 반올림 오류를 수정한다."
```

사용자 요청을 짧게 정리한 내용이다. 한두 문장으로 작성하고 요청의 핵심 변경 사항이 드러나야 한다.

### 7.2 `request.originalPrompt`

```yaml
request:
  originalPrompt: "점수 계산할 때 반올림이 이상하게 되는 것 같은데 고쳐줘."
```

사용자가 전달한 원래 요청을 기록한다. 가능하면 원문을 그대로 보존하되, 민감한 정보가 포함된 경우에는 비밀번호, 토큰, 개인정보를 그대로 기록하지 않는다.

---

## 8. 작업 범위

### 8.1 `scope.allowedPaths`

```yaml
scope:
  allowedPaths:
    - "app/scorers/**"
    - "tests/test_default_scoring_engine.py"
    - "tasks/20260810-1530-fix-scoring-bug/**"
```

이번 작업에서 생성, 수정 또는 삭제할 수 있는 파일 경로다.

작성 규칙:

- 가능한 한 구체적인 경로를 사용한다.
- 프로젝트 전체를 허용하지 않는다 (`**` 단독 금지).
- 현재 작업 디렉토리를 반드시 포함한다.
- 작업 중 범위가 늘어나면 파일 수정 전에 먼저 갱신한다.
- 범위 변경 이유를 `history`에 기록한다.

### 8.2 `scope.deniedPaths`

```yaml
scope:
  deniedPaths:
    - ".env"
    - ".env.*"
    - "secrets/**"
    - ".venv/**"
    - "__pycache__/**"
    - ".git/**"
    - "runtime/**"
    - "dist/**"
    - "build/**"
    - ".agent/**"
```

기본적으로 수정하거나 삭제할 수 없는 경로다.

`allowedPaths`에 포함되어 있더라도 `deniedPaths`에 포함된 경로는 수정하지 않는다. 사용자의 명시적인 요청이 있는 경우에만 예외적으로 변경할 수 있다.

`runtime/**`은 실행 로그·감사 데이터가 저장되는 경로이므로 코드 변경 작업에서 다루지 않는다. `.agent/**`는 작업 관리 정책·템플릿 보관 경로이므로 사용자의 명시적인 요청 없이 수정하지 않는다.

---

## 9. 요구사항

### 9.1 `requirements.items`

```yaml
requirements:
  items:
    - "ScoringResult의 contribution 합산 결과를 정수로 반올림한다."
    - "기존 소수점 이하 값을 사용하는 다른 계산에는 영향을 주지 않는다."
    - "반올림 동작을 검증하는 단위 테스트를 추가한다."
```

사용자의 요청을 검증 가능한 요구사항으로 나눈다.

작성 규칙:

- 한 항목에는 하나의 조건만 작성한다.
- 구현 후 성공 여부를 판단할 수 있어야 한다.
- 모호한 표현을 사용하지 않는다.
- 사용자 요청에 없는 요구사항을 임의로 추가하지 않는다.

---

## 10. 작업 계획

### 10.1 `plan.steps`

```yaml
plan:
  steps:
    - id: 1
      description: "현재 ScoringResult 합산 로직을 확인한다."
      status: pending

    - id: 2
      description: "반올림 로직을 수정한다."
      status: pending

    - id: 3
      description: "반올림 단위 테스트를 추가하고 실행한다."
      status: pending
```

실제 작업 순서를 기록한다. 각 단계는 `id`, `description`, `status` 필드를 가진다.

### 10.2 `plan.steps[].status`

허용 값:

```text
pending
in_progress
completed
blocked
skipped
```

| 상태 | 의미 |
|---|---|
| `pending` | 아직 시작하지 않음 |
| `in_progress` | 현재 수행 중 |
| `completed` | 정상적으로 완료됨 |
| `blocked` | 문제로 인해 진행할 수 없음 |
| `skipped` | 수행할 필요가 없어 생략됨 |

`skipped`를 사용하는 경우 생략 이유를 `history`에 기록한다.

---

## 11. 작업 결과

### 11.1 `result.summary`

작업 결과를 요약한다. 완료 전에는 `null`로 두고, `completed` 상태라면 반드시 작성한다.

### 11.2 `result.changedFiles`

```yaml
result:
  changedFiles:
    - "app/scorers/default_scoring_engine.py"
    - "tests/test_default_scoring_engine.py"
    - "tasks/20260810-1530-fix-scoring-bug/task.yaml"
```

작업 과정에서 생성, 수정 또는 삭제한 파일을 프로젝트 루트 기준 상대 경로로 기록한다. 현재 작업의 `task.yaml`을 포함하고, 실제 변경되지 않은 파일은 기록하지 않는다.

### 11.3 `result.verifications`

```yaml
result:
  verifications:
    - command: "uv run pytest tests/test_default_scoring_engine.py -q"
      result: passed
      summary: "반올림 관련 테스트 3개가 모두 성공했다."
```

실행한 테스트 또는 검증 결과를 기록한다. 각 항목은 `command`, `result`(`passed`/`failed`), `summary` 필드를 가진다.

실행하지 않은 명령을 실행했다고 기록하지 않으며, 실패한 검증을 `passed`로 기록하지 않는다. Agent의 파일 읽기 도구로 확인한 경우에는 셸 명령을 실행한 것처럼 기록하지 않고 실제 검증 방법을 그대로 적는다.

### 11.4 `result.completedAt`

작업이 완료된 시각이다. `status`가 `completed`인 경우 반드시 작성하고, 완료 전에는 `null`로 둔다.

---

## 12. 차단 정보

### 12.1 `blocker.reason` / 12.2 `blocker.requiredAction`

```yaml
status: blocked

blocker:
  reason: "OPENAI_API_KEY가 없어 smoke test를 실행할 수 없다."
  requiredAction: "테스트용 OpenAI API 키를 제공해야 한다."
```

작업이 `blocked` 상태가 된 이유와 재개에 필요한 조치를 기록한다. 정상 진행 중에는 둘 다 `null`로 둔다.

---

## 13. 작업 이력

### 13.1 `history`

```yaml
history:
  - at: "2026-08-10T15:30:00+09:00"
    status: planning
    message: "Task created"
```

작업의 주요 상태 변화와 중요 이벤트를 시간순으로 기록한다.

다음 이벤트는 반드시 기록한다.

- 작업 생성
- 구현 시작
- 테스트 시작
- 테스트 실패
- 수정 재개
- 작업 범위 변경
- 작업 차단
- 작업 취소
- 작업 완료

각 이력 항목은 `at`, `status`, `message` 필드를 가진다. `message`는 의미를 알 수 있는 구체적인 문장으로 작성한다.

좋지 않은 예시:

```yaml
message: "진행"
message: "수정"
message: "완료함"
```

좋은 예시:

```yaml
message: "Scoring rounding fix implementation started"
message: "Allowed paths expanded to include app/aggregators/default_evidence_aggregator.py"
message: "Tests failed because rounding still used banker's rounding"
```

---

## 14. 완성된 예시

```yaml
schemaVersion: 1

id: "20260810-1530-fix-scoring-bug"
title: "Stock Scoring 결과 반올림 오류 수정"
description: "ScoringResult의 contribution 합산 시 소수점 반올림이 Policy 기대값과 어긋나는 문제를 수정한다."

status: completed

createdAt: "2026-08-10T15:30:00+09:00"
updatedAt: "2026-08-10T15:55:00+09:00"

agent:
  provider: "codex"
  model: null
  sessionId: null

request:
  summary: "Stock Scoring 결과의 반올림 오류를 수정한다."
  originalPrompt: "점수 계산할 때 반올림이 이상하게 되는 것 같은데 고쳐줘."

scope:
  allowedPaths:
    - "app/scorers/default_scoring_engine.py"
    - "tests/test_default_scoring_engine.py"
    - "tasks/20260810-1530-fix-scoring-bug/**"

  deniedPaths:
    - ".env"
    - ".env.*"
    - "secrets/**"
    - ".venv/**"
    - "__pycache__/**"
    - ".git/**"
    - "runtime/**"
    - "dist/**"
    - "build/**"
    - ".agent/**"

requirements:
  items:
    - "ScoringResult의 contribution 합산 결과를 정수로 반올림한다."
    - "기존 소수점 이하 값을 사용하는 다른 계산에는 영향을 주지 않는다."
    - "반올림 동작을 검증하는 단위 테스트를 추가한다."

plan:
  steps:
    - id: 1
      description: "현재 ScoringResult 합산 로직을 확인한다."
      status: completed

    - id: 2
      description: "반올림 로직을 수정한다."
      status: completed

    - id: 3
      description: "반올림 단위 테스트를 추가하고 실행한다."
      status: completed

result:
  summary: "ScoringResult 합산 시 반올림 방식을 정수 round-half-up으로 통일하고 관련 테스트를 추가했다."

  changedFiles:
    - "app/scorers/default_scoring_engine.py"
    - "tests/test_default_scoring_engine.py"
    - "tasks/20260810-1530-fix-scoring-bug/task.yaml"

  verifications:
    - command: "uv run pytest tests/test_default_scoring_engine.py -q"
      result: passed
      summary: "반올림 관련 테스트 3개가 모두 성공했다."

  completedAt: "2026-08-10T15:55:00+09:00"

blocker:
  reason: null
  requiredAction: null

history:
  - at: "2026-08-10T15:30:00+09:00"
    status: planning
    message: "Task created"

  - at: "2026-08-10T15:35:00+09:00"
    status: in_progress
    message: "Scoring rounding fix implementation started"

  - at: "2026-08-10T15:50:00+09:00"
    status: testing
    message: "Rounding regression tests started"

  - at: "2026-08-10T15:55:00+09:00"
    status: completed
    message: "Task completed and verified"
```

---

## 15. 완료 전 점검 목록

작업 상태를 `completed`로 변경하기 전에 다음 항목을 확인한다.

```text
[ ] id가 작업 디렉토리 이름과 동일하다.
[ ] status가 올바른 상태 전이를 따랐다.
[ ] createdAt과 updatedAt이 작성되어 있다.
[ ] request에 사용자 요청이 기록되어 있다.
[ ] allowedPaths에 실제 변경 경로가 포함되어 있다.
[ ] requirements.items가 검증 가능한 문장으로 작성되어 있다.
[ ] plan.steps가 실제 수행 단계와 일치한다.
[ ] changedFiles에 모든 변경 파일이 기록되어 있다.
[ ] verifications에 실제 검증 결과가 기록되어 있다.
[ ] 검증 결과가 모두 성공했다.
[ ] result.summary가 작성되어 있다.
[ ] result.completedAt이 작성되어 있다.
[ ] history에 주요 상태 변경이 기록되어 있다.
[ ] 남아 있는 오류나 제한사항을 숨기지 않았다.
```

위 조건을 충족하지 못하면 `completed`로 변경하지 않는다.
