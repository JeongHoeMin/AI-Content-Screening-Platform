# PR #1 Core Contract and CollectPostsSkill

## Summary

- Project-wide core Skill contract is introduced before adding feature-specific Skills.
- `CollectPostsSkill` is implemented as the first Skill on top of the contract.
- The Skill collects posts from providers, normalizes raw posts, and returns factual observation results.
- The Skill does not perform AI judgment, deduplication, ranking, storage, or prompt usage.

## Key Changes

- `app/core` defines:
  - `Skill`
  - `SkillRequest`
  - `SkillResult`
  - `SkillMetadata`
  - `SkillError`
- `app/models` defines:
  - `CommunityType`
  - `Post`
  - `RawPost`
  - `RawRedditPost`
  - `RawDcInsidePost`
  - `NormalizeResult`
  - CollectPosts request/data/metadata models
- `app/providers` defines:
  - `CommunityProvider`
  - `CommunityNormalizer`
  - `ProviderRegistry`
  - `NormalizerRegistry`
  - mock providers and normalizers
- `CollectPostsSkill`:
  - receives registries through constructor injection
  - runs providers concurrently
  - normalizes provider results
  - returns `SkillResult[CollectPostsData, CollectPostsMetadata]`

## Design Rules

- Skill interface is `async execute(request) -> SkillResult`.
- Skill does not mutate shared state.
- Harness owns state changes.
- Agent calls Skills only.
- Provider collects raw data.
- Normalizer converts raw data into common domain models.
- New providers and normalizers should be added through registry registration, not Skill branching.

## Test Plan

- Core contract model validation.
- Provider registry and normalizer registry lookup.
- Provider parallel execution.
- Provider failure does not stop successful providers.
- All providers failing raises an unrecoverable exception.
- Normalizer failure is recorded as recoverable error metadata.

## Out of Scope

- Real Reddit/DCInside/Ruliweb integration.
- LLM calls.
- Prompt usage.
- Database or cache storage.
- LangGraph integration.
