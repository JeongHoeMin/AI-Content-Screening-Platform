# PR-39 — LLM Retry, Failure Observability, and Local Logs v1

## Goal

Make OpenAI workflow failures traceable without recording article bodies, prompts,
credentials, or raw provider responses. Retry transient LLM failures at most three
times for the same workflow stage and input, then show a safe terminal explanation
in the dashboard.

## Decisions

- `extract`, `screen`, and `cross_validate` are the only retryable workflow stages.
- A stage receives at most three attempts. Timeout, connection, authentication, and
  authorization failures exhaust the workflow after the third failure.
- Invalid structured output, parser failures, and oversized request failures preserve
  valid sibling work. Cross-validation falls back to insufficient evidence.
- Docker persists safe JSONL application and execution-audit logs at
  `./runtime/logs`, which is never committed.
- Cross validation deterministically limits evidence to five articles per event and
  two candidates per LLM batch.

## Change log

- 2026-07-31: Approved implementation plan created.
