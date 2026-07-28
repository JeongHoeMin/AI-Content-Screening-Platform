# PR #3 Harness Execution Pipeline

## Summary

- `Harness` is introduced as the shared entrypoint for running Skills.
- Harness v1 is intentionally minimal.
- It delegates execution to `skill.execute(request)` without adding policy behavior.
- Harness is stateless.

## Key Changes

- `app/harness` package is added.
- `Harness.run()` signature:

```python
async def run(
    self,
    skill: Skill[RequestT, DataT, MetadataT],
    request: RequestT,
) -> SkillResult[DataT, MetadataT]:
    ...
```

- Current implementation:

```python
return await skill.execute(request)
```

## Design Rules

- Harness stores no execution state.
- `run()` uses only the provided Skill and Request.
- The same Harness instance can be reused across many runs without state leakage.
- Skill generic types and SkillResult generic types are preserved.

## Test Plan

- Harness execution matches direct Skill execution.
- Reusing one Harness instance for multiple requests does not leak previous results.
- Tests use async style through the existing `anyio` pytest plugin.

## Out of Scope

- Hooks.
- Retry.
- Logging.
- Metrics.
- Tracing.
- LangGraph.
- Workflows.
- Multi-Skill execution.
- Parallel execution.
- Event system.
- DI container.
