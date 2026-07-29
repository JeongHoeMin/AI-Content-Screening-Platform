# PR-27 OpenAI News Event Screener

## Summary

OpenAI mode evaluates extracted news events with structured LLM output before
the existing deterministic screening policy makes an accept, review, or reject
decision. Mock mode and the public CLI JSON schema remain unchanged.

## Contract

The LLM returns a batch-local `event_index`, relevance, importance,
credibility, cross-validation requirement, and concise reasons. Scores are JSON
numbers only: integer values and integral float values are converted to the
existing 0--100 integer domain scores. The parser restores event identity and
input order; the policy alone makes final decisions.

`credibility` evaluates the supplied article evidence and source quality. It is
not the extractor's `confidence`, which reports support for extraction.

## Failure and observability policy

Invalid individual assessments are excluded without fabricating fallback
scores. The parser returns structured, non-sensitive error observations and the
screener logs only batch index, event index, internal candidate ID, and error
kind. It never logs article content, prompts, raw provider responses, or API
keys. Batch provider/response failures do not stop later batches. If input
events exist but no valid decision is produced, the screener raises
`NoValidScreeningDecisionsError`.

## OpenAI assembly and smoke test

Extractor and screener share the OpenAI structured-output client. The current
structured LLM gateway receives its response model per request and is also safe
to share; a future stateful gateway must be instantiated per task while keeping
the client shared.

Run the automated checks with `uv run pytest`, `uv run python -m compileall app
tests`, and `git diff --check`. With valid OpenAI configuration, run
`uv run screening --mode openai --input examples/openai-screening-articles.json`.
Verify integer scores, evidence-grounded reasons, appropriate cross-validation
explanations, no investment advice, and resistance to prompt-injection text.

## Implementation record

2026-07-29: The response boundary uses strict JSON numeric values while the
parser owns 0--100 and integral-value validation. This preserves valid sibling
events when one score is invalid. The final result omits recoverable screening
errors by design; limited structured logs preserve operational observability
without exposing article or provider payloads.

2026-07-29: Response DTO indexes are strict integers but deliberately have no
non-negative constraint. The parser records negative and out-of-range indexes
as event-level observations, retaining valid siblings. Cross-validation flags
are strict JSON booleans, and candidate IDs are indexed once per screening run
to preserve the internal identity invariant.

2026-07-29: Transport DTO fields deliberately preserve malformed primitive
values so the parser can record event-level errors without discarding valid
siblings. Batch-level failures are provider calls, structured-output response
failures, or invalid response roots; field types, indexes, scores, flags, and
reasons are event-level failures.

Event-index type errors, including strings, booleans, and null, are recorded as
`INVALID_EVENT_INDEX`. They cannot be mapped to an actual candidate, so their
`candidate_id` remains `None`.
