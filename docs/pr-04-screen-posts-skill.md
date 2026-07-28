# PR #4 ScreenPostsSkill

## Summary

- `ScreenPostsSkill` is introduced to select shorts candidates from collected posts.
- Real LLMs are not used.
- Screening judgment is delegated to a pluggable `PostEvaluator`.
- `ScreenPostsSkill` filters evaluation results using `is_candidate=True`.

## Key Changes

- `app/models/screen_posts.py` adds:
  - `ScreenPostsRequest`
  - `ScreeningResult`
  - `PostEvaluationResult`
  - `ScreenPostsData`
  - `ScreenPostsMetadata`
- `app/evaluators` package adds:
  - `PostEvaluator`
  - `MockPostEvaluator`
- `ScreenPostsSkill` is added.

## Model Semantics

- `PostEvaluationResult.posts` means evaluation results for all input posts.
- `ScreenPostsData.candidates` means final shorts candidates only.
- `ScreeningResult` contains:
  - `post`
  - `score`
  - `is_candidate`
  - `reasons`
- `reasons` are human-readable natural language explanations, not enum values or internal codes.

## Design Rules

- `PostEvaluator.evaluate(posts)` evaluates a list of posts at once.
- `PostEvaluator` implementations are stateless.
- `ScreenPostsSkill` calls `evaluator.evaluate(request.posts)`.
- `ScreenPostsSkill` only filters `is_candidate=True`.
- No candidate limit, score sorting, category balancing, or diversity logic is included.
- Future candidate selection policy extensions belong in `ScreenPostsSkill`, not `PostEvaluator`.

## Test Plan

- Mock evaluator returns `PostEvaluationResult`.
- Scores are within `0..100`.
- Reasons are human-readable strings.
- `ScreenPostsSkill` includes only candidates.
- Input order is preserved.
- Metadata records total posts and candidate posts.
- Evaluator failures are propagated.
- Harness execution works.

## Out of Scope

- Real LLM calls.
- Prompt engineering.
- OpenAI, Claude, Gemini integration.
- LangGraph.
- Workflow.
- Advanced AI evaluation logic.
- RAG.
- Vector search.
