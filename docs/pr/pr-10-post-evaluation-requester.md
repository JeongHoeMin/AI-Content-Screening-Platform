# PR #10 Post Evaluation Requester 도입

## Summary

- `LLMPostEvaluationRequester`를 추가해 PromptBuilder와 LLMClient를 실제로 연결한다.
- Requester는 오케스트레이션만 담당하며 Prompt 생성과 응답 해석은 수행하지 않는다.
- `PostEvaluationRequester.request()`의 행동 계약을 Protocol 문서로 고정한다.
- 테스트 Fake도 PromptBuilder와 LLMClient 추상 계약을 명시적으로 구현한다.
- 기존 `PostEvaluator`와 `ScreenPostsSkill`은 변경하지 않는다.

## Responsibilities

Requester는 PromptBuilder에 게시글을 전달하고, 변경하지 않은 메시지 컬렉션을 LLMClient에 전달한 뒤 변경하지 않은 `ChatResponse`를 반환한다.

Requester는 PromptTemplate 접근, JSON 직렬화, 응답 파싱, `PostEvaluationResult` 생성, GenerationConfig 정책, Provider SDK, Retry, Guardrail을 담당하지 않는다.

## Implementation Changes

- `PostEvaluationRequester` Protocol과 `LLMPostEvaluationRequester` 구현체를 추가한다.
- 구현체는 `LLMClient`와 `PromptBuilder[EvaluatorPromptInput]` 추상 계약을 생성자 주입으로 받는다.
- `request()`는 입력 게시글로 DTO를 만들고 Builder를 한 번 호출한 뒤, 동일 메시지 객체를 `LLMClient.chat(messages=..., config=None)`에 전달한다.
- LLMClient의 동일 `ChatResponse` 객체를 그대로 반환하고 예외를 wrapping하지 않는다.
- 새 타입은 `app.evaluators`에서 export한다.

## Test Plan

- FakePromptBuilder와 FakeLLMClient로 DTO 전달, 메시지 identity, `config=None`, 응답 identity, 예외 전파를 검증한다.
- FakePromptBuilder는 `PromptBuilder[EvaluatorPromptInput]`를, FakeLLMClient는 `LLMClient`를 구현한다.
- Prompt 문자열, 메시지 구조, JSON 직렬화는 PromptBuilder 테스트에 남긴다.
- `UV_CACHE_DIR=.uv-cache uv run pytest`를 실행한다.

## Success Criteria

- Requester는 PromptBuilder와 LLMClient의 추상 계약에만 의존한다.
- `request()`의 행동 계약은 구현체와 독립적으로 문서화된다.
- Requester는 ChatMessage 컬렉션 타입을 독자적으로 정의하지 않고 LLMClient 계약과 일치시킨다.
- 테스트 Fake는 구현체가 아닌 추상 계약을 기준으로 Requester를 검증한다.
- 기존 평가 결과 계약과 ScreenPostsSkill 동작은 변경되지 않는다.
- 전체 테스트가 통과한다.

## Assumptions

- Requester는 읽기 전용 `Sequence[Post]`를 입력으로 받는다.
- Requester는 ChatMessage 컬렉션 타입을 LLMClient 계약과 동일하게 사용하며 별도 컬렉션 타입 정책을 두지 않는다.
- LLMClient가 향후 `Sequence[ChatMessage]`를 지원하면 Requester도 동일하게 변경한다.
- `GenerationConfig` 정책과 `ChatResponse` 파싱은 후속 PR에서 추가한다.
- `LLMPostEvaluator`와 `PostEvaluationParser`는 PR #11에서 도입한다.

## Commit Message

```text
feat: connect prompt builder to llm requester
```

## Change Log

### 2026-07-29

- 테스트 Fake가 실제 구현체와 같은 PromptBuilder 및 LLMClient Protocol을 명시적으로 구현하도록 변경했다.
- `PostEvaluationRequester.request()` docstring을 역할 중심 행동 계약으로 보강했다.
- Requester의 ChatMessage 컬렉션 타입은 LLMClient 계약을 따르며 별도 정책을 갖지 않는다는 점을 명시했다.
