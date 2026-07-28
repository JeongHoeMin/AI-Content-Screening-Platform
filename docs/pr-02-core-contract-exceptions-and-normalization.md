# PR #2 Core Contract Exceptions and Normalization Metadata

## Summary

- Core Contract v1 is refined with project-specific exceptions and explicit Skill stages.
- Registry lookup no longer exposes generic `KeyError`.
- Normalizers are converted to async contracts.
- `normalize_error_count` semantics are clarified.

## Key Changes

- `app/core/exceptions` adds:
  - `SkillExecutionError`
  - `AllProvidersFailedError`
  - `ProviderNotFoundError`
  - `NormalizerNotFoundError`
- `SkillStage` is introduced with only currently used stages:
  - `PROVIDER_COLLECT`
  - `NORMALIZE`
- `SkillError.stage` uses `SkillStage` instead of plain strings.
- `CommunityNormalizer.normalize()` becomes async.
- `ProviderResultMetadata.normalize_error_count` is added.
- `ProviderExecution` is represented as a slotted dataclass.

## Design Rules

- Recoverable failures are represented as `SkillError`.
- Unrecoverable failures use project-specific exceptions.
- Registry lookup failures are recorded as errors where recoverable.
- `normalize_error_count` counts only RawPost to Post conversion failures.
- Normalizer registry lookup failure is recorded in `errors` but is not included in `normalize_error_count`.
- `SkillStage` remains `class SkillStage(str, Enum)` for Python 3.9 compatibility.

## Test Plan

- Missing provider raises `ProviderNotFoundError`.
- Missing normalizer raises `NormalizerNotFoundError`.
- All provider failures raise `AllProvidersFailedError`.
- `SkillError.stage` stores a `SkillStage`.
- Async normalizer flow is awaited correctly.
- Normalization conversion failures increment `normalize_error_count`.
- Normalizer lookup failure does not increment `normalize_error_count`.

## Out of Scope

- New Core Contract features beyond exception/stage cleanup.
- Resolver introduction.
- Harness changes.
- Real provider integration.
