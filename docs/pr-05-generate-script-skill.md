# PR #5 GenerateScriptSkill

## Summary

- `GenerateScriptSkill` is introduced to generate scripts from screened candidates.
- Real LLMs are not used.
- Script generation is delegated to a pluggable `ScriptGenerator`.
- `GenerateScriptSkill` wraps generator output without adding business logic.

## Architecture

```text
CollectPostsSkill -> Post[] -> ScreenPostsSkill -> ScreeningResult[] -> GenerateScriptSkill -> GeneratedScript[]
```

## Key Changes

- `app/models/generate_script.py` adds:
  - `GenerateScriptRequest`
  - `GeneratedScript`
  - `ScriptGenerationResult`
  - `GenerateScriptData`
  - `GenerateScriptMetadata`
- `app/generators` package adds:
  - `ScriptGenerator`
  - `MockScriptGenerator`
- `GenerateScriptSkill` is added.

## Model Semantics

- `GenerateScriptRequest.candidates` receives `ScreenPostsSkill` candidates.
- `GeneratedScript` represents a generated script and stores the original `Post`.
- `GeneratedScript` does not directly depend on `ScreeningResult`.
- `ScriptGenerationResult` is generator output.
- `GenerateScriptData` is Skill business output.

## Design Rules

- `ScriptGenerator.generate(candidates)` receives the full candidate list at once.
- `ScriptGenerator` performs internal iteration.
- `GenerateScriptSkill` does not loop over candidates.
- `GenerateScriptSkill` does not generate scripts itself.
- `MockScriptGenerator` is stateless.
- `MockScriptGenerator` uses only simple templates.
- Empty candidates return `ScriptGenerationResult(scripts=[])`.
- Prompt creation, AI model selection, external API calls, quality judgment, and post-processing are not implemented.

## Test Plan

- Mock generator returns `ScriptGenerationResult`.
- Generated script count matches candidate count.
- Each script has title, hook, body, and ending.
- `GeneratedScript.post` references the original `Post`.
- Empty candidate input returns an empty script list.
- Skill delegates to generator once.
- Skill returns generation scripts unchanged.
- Metadata records total candidates and generated scripts.
- Generator failures are propagated.
- Harness execution works.

## Out of Scope

- OpenAI API.
- Claude API.
- Gemini API.
- Prompt engineering.
- Workflow.
- LangGraph.
- Script quality evaluation.
- Script regeneration.
- Image generation.
- TTS.
- Retry.
- Partial success.
