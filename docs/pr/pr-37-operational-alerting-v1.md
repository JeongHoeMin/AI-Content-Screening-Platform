# PR-37 — Operational Alerting v1

## 목표

Harness가 terminal workflow audit에서 즉시 조치가 필요한 안전한 운영 alert를 결정하고, 주입된 delivery sink로 전달한다. alert 판단은 Policy가 소유하고, 외부 전달 실패는 screening workflow 결과나 audit persistence를 바꾸지 않는다.

## 범위

- immutable alert Domain, severity/type, duration threshold config와 deterministic Policy를 추가한다.
- `FAILED` execution 및 설정된 최대 duration 초과 execution을 alert로 만든다.
- audit sink decorator는 먼저 audit record를 durable sink에 append한 뒤, Policy 결과를 notifier로 best-effort 전달한다.
- JSONL alert sink와 CLI opt-in `--alert-log`/`--alert-max-duration-seconds`를 추가한다. alert log는 audit log와 함께 명시돼야 한다.
- notifier 실패를 safe structured log로 관측하고, raw exception/기사 내용은 저장·로그하지 않는다.

## 비범위

- Slack/email/webhook provider, alert grouping/dedup/escalation, failure-rate window policy, acknowledgement UI, pager/on-call routing, alert persistence retry는 후속 작업이다.
- Policy, Workflow, LLM, recommendation 결과 및 CLI success JSON schema는 바꾸지 않는다.

## 설계 결정

1. `FAILED`는 critical, latency breach는 warning이다. 한 execution이 두 조건을 모두 만족하면 두 atomic alert를 보존한다.
2. audit append가 먼저 성공해야 alert delivery를 시도한다. audit sink failure는 PR-34 contract대로 execution failure이며 alert는 보내지 않는다.
3. notifier failure는 best-effort delivery failure로서 workflow를 실패시키지 않는다. type과 alert id만 로그에 남긴다.
4. alert record에는 execution ID/mode, safe duration/input count, bounded error type과 threshold만 담고 기사·prompt·raw exception을 담지 않는다.

## 구현 순서

1. alert Domain/Policy/notifier and audit-sink decorator를 추가한다.
2. JSONL delivery 및 CLI opt-in 조립을 추가한다.
3. policy, ordering, notifier isolation, CLI regression, 전체 suite을 검증한다.

## 변경 이력

- 2026-07-30: 최초 계획 작성. 외부 notification provider는 secret/credential lifecycle과 함께 별도 작업으로 분리했다.
