# PR #11 LLM Post Evaluator 및 ID 기반 Evaluation Parser 도입

## Summary

- `EvaluationResponse`를 PromptTemplate, LLM, Parser가 공유하는 응답 계약으로 추가한다.
- `DefaultPostEvaluationParser`는 ID 기반 LLM 응답을 원본 Post와 매핑해 도메인 결과를 조립한다.
- `LLMPostEvaluator`는 Requester와 Parser만 오케스트레이션한다.
- 기존 `ScreeningResult` 정책은 유지하고 `EvaluationValidator`는 PR #12에서 도입한다.

## Response Contract

- LLM은 `post_id`, `score`, `is_candidate`, `reasons`를 가진 `EvaluationResponse` JSON만 반환한다.
- 응답은 모든 입력 Post의 ID를 정확히 한 번씩 포함하고, 원본 Post 전체나 추가 속성, Markdown fence, 설명 텍스트를 포함하지 않는다.
- `post_id`는 입력 Post의 ID를 그대로 사용한다.

## Implementation Changes

- `EvaluationResponse` DTO, Parser Protocol, 기본 JSON Parser, `LLMPostEvaluator`를 추가한다.
- Parser는 JSON 파싱, DTO 생성, 엄격한 ID 매핑, 기존 도메인 모델 조립만 담당한다.
- 매핑이 성공한 뒤에만 입력 순서대로 `PostEvaluationResult`를 생성한다.
- LLMPostEvaluator는 Requester와 Parser의 추상 계약만 생성자 주입으로 사용한다.
- Evaluator PromptTemplate의 내부 문자열만 응답 계약에 맞게 갱신한다.

## Test Plan

- Parser의 정상 매핑, 입력 순서 보존, JSON·shape·ID 매핑 실패 전파를 검증한다.
- Evaluator의 Requester/Parser 호출, 객체 identity, 예외 전파를 Fake Protocol 구현체로 검증한다.
- PromptTemplate이 ID 기반 JSON 전용 응답과 추가 필드 금지를 지시하는지 검증한다.
- `UV_CACHE_DIR=.uv-cache uv run pytest`를 실행한다.

## Assumptions

- Partial Success는 지원하지 않으며 ID 매핑 실패는 `ValueError`로 처리한다.
- 전용 Mapping Exception은 오류 체계 정리 후속 PR에서 도입한다.
- Structured Output, Retry, Guardrail, EvaluationValidator는 후속 PR 범위다.

## Commit Message

```text
feat: add llm post evaluator and parser
```
