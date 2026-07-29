# PR-25 OpenAI Event Extractor

## Summary

`openai` execution mode uses an OpenAI Responses API structured-output adapter
only for Event extraction. Screening, cross validation, resolution, analysis,
scoring, and recommendations retain the deterministic Mock/Rule implementations.

## Configuration and execution

Required environment variable:

```text
OPENAI_API_KEY
```

Optional variables and defaults:

```text
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=2
```

No dotenv file is loaded automatically.

```bash
OPENAI_API_KEY="..." uv run screening \
  --mode openai \
  --input examples/openai-articles.json
```

## Architecture

The OpenAI adapter calls `AsyncOpenAI.responses.parse` with the system prompt,
user prompt, and Pydantic response model. It verifies a completed response and
returns only `output_parsed`; OpenAI SDK response types do not leave the adapter.

The Prompt Builder assembles messages, the prompt template renders explicit
Article ID/Source/Title/Published at/Content fields, and the Parser converts
typed response data to domain Events. Article content is untrusted data, not
instructions.

The parser collapses whitespace, drops empty values, preserves first spelling
while de-duplicating companies, industries, and keywords case-insensitively,
and de-duplicates reasons by exact normalized text. `confidence` describes the
model's extraction confidence, not the factual truth of the event.

## Failure policy

- Invalid individual Events are omitted and recorded as recoverable errors.
- API errors, refusal, incomplete/failed responses, absent parsed output, and
  whole-response parsing failures omit only their batch.
- A completed batch with `events=[]` succeeds.
- The workflow continues when one or more batches complete successfully and
  raises an execution error only when every attempted batch fails.

## Test strategy and exclusions

Unit tests use fake SDK clients; no automated test calls the OpenAI service.
This PR excludes OpenAI screeners and validators, article collection, crawling,
web search, RAG, persistence, scheduling, UI, event clustering, ticker
inference, dotenv loading, prompt versioning, and cost tracking.
