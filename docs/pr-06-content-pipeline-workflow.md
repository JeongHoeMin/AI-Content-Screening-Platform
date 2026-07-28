# PR #6 ContentPipelineWorkflow

## Summary

- `ContentPipelineWorkflow` is introduced to run multiple Skills as one sequential pipeline.
- Workflow uses Harness for Skill execution.
- Workflow manages only Skill order and data passing.
- Final output is `ContentPipelineResult`, not raw SkillResult objects.

## Architecture

```text
ContentPipelineWorkflow
        |
        v
      Harness
        |
        v
CollectPostsSkill -> ScreenPostsSkill -> GenerateScriptSkill
        |
        v
ContentPipelineResult
```

## Key Changes

- `app/models/workflow.py` adds:
  - `ContentPipelineRequest`
  - `ContentPipelineResult`
- `app/workflows` package adds:
  - `Workflow`
  - `ContentPipelineWorkflow`

## Request And Result

- `ContentPipelineRequest` contains:
  - `sources: List[CommunityType]`
  - `limit: int`
  - `period: timedelta`
  - `category: Optional[str]`
- No separate `Source` model is introduced.
- `ContentPipelineResult` contains:
  - `posts`
  - `candidates`
  - `scripts`

## Execution Flow

1. Build `CollectPostsRequest` from `ContentPipelineRequest`.
2. Run `CollectPostsSkill` through Harness.
3. Pass collected posts into `ScreenPostsRequest`.
4. Run `ScreenPostsSkill` through Harness.
5. Pass candidates into `GenerateScriptRequest`.
6. Run `GenerateScriptSkill` through Harness.
7. Return composed `ContentPipelineResult`.

## Design Rules

- Workflow receives Harness and all Skills through constructor injection.
- Workflow does not create Harness.
- Workflow does not create Skills.
- All Skill execution goes through `harness.run()`.
- Workflow is sequential.
- Workflow does not store state.
- Workflow does not return SkillResult.
- Workflow propagates failures without partial success handling.

## Test Plan

- Use Harness test double.
- Use Skill test doubles.
- Verify execution order: collect, screen, generate.
- Verify collect data is passed to screen request.
- Verify screen candidates are passed to generate request.
- Verify `ContentPipelineResult` composition.
- Verify collect failure stops screen and generate.
- Verify screen failure stops generate.
- Verify generate failure is propagated.

## Out of Scope

- OpenAI API.
- Claude API.
- Gemini API.
- Prompt engineering.
- Retry.
- Guardrail.
- Reflection.
- Model routing.
- LangGraph.
- Parallel execution.
- Partial success.
- Workflow state storage.
- Core Contract changes.
- Harness changes.
- Existing Skill changes.
