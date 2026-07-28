# PR #9 PromptBuilder 도입 계획

## Summary

- Generic `PromptBuilder` 계약과 첫 구현인 `EvaluatorPromptBuilder`를 추가한다.
- PromptBuilder는 내부 DTO와 Template 함수로 `ChatMessage`만 조립한다.
- 템플릿 치환과 게시글 JSON 표현은 PromptTemplate 계층에 둔다.
- 기존 Evaluator, Generator, Skill, LLMClient 호출 흐름은 변경하지 않는다.

## Implementation Changes

- `AGENTS.md`의 Prompt Management 규칙을 PromptBuilder 코드와 Python PromptTemplate의 분리 구조에 맞게 개정한다.
- `app/prompts/`에 `PromptBuilder[InputT]`, immutable `EvaluatorPromptInput`, `EvaluatorPromptBuilder`를 추가한다.
- `app/prompt_templates/`에 Evaluator 시스템/사용자 템플릿 상수와 문자열 생성 함수를 추가한다.
- Builder는 `SYSTEM`, `USER` 순서의 두 `ChatMessage`만 조립하고 JSON 직렬화나 템플릿 치환을 직접 수행하지 않는다.

## Test Plan

- Evaluator 입력 DTO의 불변성, Generic 계약 사용, 메시지 순서와 role을 검증한다.
- Template 함수의 JSON 직렬화, 입력 반영, 빈 목록 처리를 검증한다.
- 기존 테스트를 변경하지 않고 `UV_CACHE_DIR=.uv-cache uv run pytest`를 실행한다.

## Success Criteria

- PromptBuilder는 Builder별 전용 입력 DTO를 지원하는 Generic Protocol이다.
- PromptBuilder와 PromptTemplate의 문자열 생성 책임이 분리된다.
- PromptBuilder는 Provider나 LLMClient에 의존하지 않는다.
- 기존 실행 흐름을 변경하지 않고 전체 테스트가 통과한다.

## Assumptions

- `EvaluatorPromptInput`은 검증이 끝난 데이터를 전달하는 내부 immutable DTO이며 표준 `@dataclass(frozen=True)`를 사용한다.
- PromptTemplate은 Prompt 표현 방식(JSON)을 결정한다.
- EvaluatorPromptBuilder를 기존 Evaluator에 실제 주입하거나 LLM 호출을 연결하는 작업은 다음 PR로 미룬다.

## Commit Message

```text
feat: introduce prompt builder abstraction
```

## Change Log

### 2026-07-29

- PromptTemplate의 공개 API는 `build_evaluator_system_prompt()`와 `build_evaluator_user_prompt()`로 제한했다. 템플릿 문자열 상수와 직렬화 helper는 모듈 내부 구현으로 관리한다.
- `EvaluatorPromptInput.posts`와 사용자 Prompt 생성 함수의 입력을 `Sequence[Post]`로 변경해 읽기 전용 입력 계약을 명확히 했다.
- 게시글 JSON 표현은 PromptTemplate 내부 `_serialize_posts_for_prompt()` helper로 분리했다. PromptBuilder는 Template 함수 호출과 `ChatMessage` 조립만 담당한다.
