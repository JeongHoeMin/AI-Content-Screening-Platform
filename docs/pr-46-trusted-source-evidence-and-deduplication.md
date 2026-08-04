# PR-46 — Trusted source, evidence, and deduplication delivery plan

## Goal

Deliver trusted full-text collection, verifiable event evidence, and conservative
event deduplication in three independently reviewable feature branches.

## Delivery order

1. `codex/storage-persistence`: Docker Compose PostgreSQL, validated database
   configuration, and the harness-owned persistence foundation.
2. `codex/trusted-input-evidence`: OpenDART full text, configured IR RSS,
   input-quality filtering, and validated extraction evidence.
3. `codex/event-deduplication`: deterministic candidate generation, structured
   LLM same-event observations, and policy-owned canonical event selection.

## Security and scope

- Full text may be stored in PostgreSQL but must never be emitted through
  structlog, JSONL execution audits, prompts outside the target inference call,
  or exception messages.
- The initial full-text sources are OpenDART and explicitly configured corporate
  IR RSS feeds. Naver News remains discovery-only.
- The database is a Docker Compose `postgres` service backed by the named
  `postgres_data` volume.
- LLM output is an observation only. Parser and Policy own validation and
  decisions. A same-event observation below confidence 80 never merges events.
- Publisher HTML scraping, embedding similarity, human review queues, and
  automatic retention deletion are not included in this delivery.

## Change log

- 2026-08-04: Plan approved. Split into dependency-ordered feature branches so
  each branch can be verified, committed, and reviewed independently.
