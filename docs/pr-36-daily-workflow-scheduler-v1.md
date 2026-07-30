# PR-36 — Daily Workflow Scheduler v1

## 목표

Phase 9의 daily execution 요구를 Harness가 소유하는 UTC scheduler contract로 제공한다. 매일 같은 UTC 시각에 주입된 실행 함수를 호출하고, 한 번의 실행 실패가 이후 일정을 중단시키지 않도록 한다.

## 범위

- immutable Pydantic `DailySchedule`과 다음 UTC 실행 시각 계산을 추가한다.
- scheduler는 현재 시각과 target이 같을 때 즉시 실행하지 않고 다음 날을 선택한다.
- long-running scheduler는 stop event를 통해 대기 중 안전하게 종료되고, callback 예외는 안전한 error type 로그만 남긴 뒤 다음 실행을 예약한다.
- concurrent `run_pending` 호출은 lock으로 직렬화해 중복 실행을 방지한다.
- UTC/자정/경계값/실패 복구/stop/중복 방지를 테스트한다.

## 비범위

- CLI daemon command, cron/OS service installation, local-time zone 및 DST, retry/backoff policy, distributed lock, job persistence, multi-process leader election은 후속 작업이다.
- Scheduler는 기사 수집, LLM 호출, Policy 판단, audit file I/O를 직접 수행하지 않는다. 주입된 Harness execution callback만 호출한다.

## 설계 결정

1. v1 schedule은 `hour`/`minute` UTC만 지원한다. local timezone/DST 의미를 암묵적으로 도입하지 않는다.
2. `run_pending()`은 caller가 제공한 current time을 기준으로 due 여부를 판단하고, 성공·실패와 관계없이 다음 due time으로 advance한다. 따라서 실패한 job은 같은 slot에서 무한 반복되지 않는다.
3. `serve()`만 sleep/stop-event lifecycle을 소유한다. callback은 완료되기 전 중복 실행되지 않고 scheduler가 callback의 raw exception/message를 저장하지 않는다.
4. Scheduler의 structured log에는 schedule time과 error type만 포함한다.

## 구현 순서

1. schedule model과 scheduler lifecycle을 Harness에 추가한다.
2. deterministic clock/sleep/callback fake로 lifecycle을 테스트한다.
3. 전체 suite, compileall, diff check 후 독립 커밋한다.

## 변경 이력

- 2026-07-30: 최초 계획 작성. 파일 입력을 매일 반복하는 CLI daemon은 collection source lifecycle을 별도 설계해야 하므로 이번 단위에서 제외했다.
