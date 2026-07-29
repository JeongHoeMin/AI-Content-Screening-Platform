# PR #21 Screening Policy v1

## Goal

PR #21 adds the first AI screening policy after news event extraction. It
records whether each extracted event is accepted, requires review, or rejected
without changing the existing Resolver, Analyzer, Aggregator, Scorer, or
Recommendation pipeline.

## Assessment and Decision Boundary

The LLM returns only a typed `ScreeningAssessment`: relevance, importance,
credibility, whether cross validation is required, and user-readable reasons.
It never returns a final decision.

`ScreeningPolicy` owns every final `ACCEPT`, `REVIEW`, and `REJECT` decision.
Its default, configurable policy is evaluated in this fixed order:

1. Reject when relevance or importance is below 40.
2. Review when cross validation is required.
3. Accept when relevance, importance, and credibility are all at least 70.
4. Review in every other case.

Thresholds belong to immutable `ScreeningPolicyConfig`, so a policy can be
adjusted through dependency configuration without modifying the algorithm.

## Workflow Boundary

The private workflow graph runs `Extract -> Screen Events -> Resolve`. Nodes
return only newly produced state fields and never mutate input state. Screening
decisions preserve the identical `NewsEvent` instances created by extraction.

Decisions are observational in this PR. A `REJECT` decision does not remove an
event or alter downstream deterministic domain processing. `ScreeningResult`
returns the decisions separately from the Recommendation result.

Workflow statistics are calculated from final decisions. The accepted, review,
and rejected counts always add up to the total number of decisions.

## LLM and Parsing Boundary

`EventScreener` receives article-level inference snapshots so prompts retain
the source article context. It batches event candidates internally, delegates
prompt creation to a PromptBuilder, and receives only typed Pydantic output
from `StructuredOutputLLM`.

The parser validates missing, unknown, duplicate, and mismatched candidate IDs
and restores the original event order before policy evaluation. It does not
create replacement `NewsEvent` objects. Empty event input skips the LLM call.

Prompts request concise user-readable rationales, never private chain of
thought or internal reasoning.

## Scope Limits and Follow-up

This PR does not perform cross validation, web search, event filtering,
ranking, recommendation policy changes, retry, partial success, or batch
execution metadata expansion. Future work can add cross-validation services,
retry and recovery policy, and decision-driven downstream routing without
changing the Assessment-to-Policy ownership boundary.
