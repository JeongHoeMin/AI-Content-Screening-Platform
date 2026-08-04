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
- 2026-08-04: The dashboard image now includes Alembic artifacts and the lockfile
  declares migration dependencies. Alembic prefers the runtime `DATABASE_URL`;
  a fresh Compose PostgreSQL smoke run reached revision `20260804_01` after its
  healthcheck succeeded.
- 2026-08-04: OpenDART original-document collection now retrieves the bounded
  ZIP response per receipt number and rejects any archive containing an unsafe
  member path. Naver search responses remain discovery-only and are rejected
  before extraction through `analysis_eligible=False`.
- 2026-08-04: `IR_RSS_FEEDS`, `ARTICLE_MIN_BODY_LENGTH`, and
  `ARTICLE_MAX_BODY_LENGTH` now have a Pydantic configuration contract. RSS
  transport and runtime registration remain in the next trusted-input commit.
- 2026-08-04: Configured IR RSS and Atom feeds are now collected through an
  injected text transport. GUID or Atom ID is retained as the external identity,
  and only the configured feed endpoint is read; HTML bodies are normalized into
  numbered paragraph candidates before Article conversion.
- 2026-08-04: Input quality filtering now applies the configured minimum and
  maximum normalized-body limits at the evaluator boundary. Official full text
  without numbered paragraphs is rejected before LLM extraction; discovery-only
  Naver results remain ineligible. This is a structural policy only and does not
  infer relevance or importance.
- 2026-08-04: The deduplication node now generates deterministic candidates,
  invokes a bounded Structured Output same-event comparator only for those
  pairs, validates candidate indexes and observations, then lets Policy merge
  only `same` observations at confidence 80 or above. Mock mode remains
  conservative and returns `uncertain` rather than asserting event identity.
