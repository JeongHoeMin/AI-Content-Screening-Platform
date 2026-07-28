# PR #8 OpenAIClient 구현 계획

## Summary

- `LLMClient`의 첫 실제 Provider 구현체인 `OpenAIClient`를 추가한다.
- OpenAI SDK 의존성은 `app/llms/openai.py` 내부에만 둔다.
- `ChatMessage`와 `GenerationConfig`를 현재 사용하는 OpenAI SDK 요청 형식으로 변환하고, SDK 응답 텍스트를 `ChatResponse`로 반환한다.
- 모델 선택은 `OpenAIClient` 생성자에서 관리한다.

## Implementation Changes

- `app/llms/openai.py`에 `OpenAIClient(LLMClient)`를 추가한다.
  - 생성자는 `AsyncOpenAI` 인스턴스와 모델명을 주입받으며 SDK 인스턴스를 생성하지 않는다.
  - `chat()`은 메시지와 설정을 요청 형식으로 변환하고, 현재 사용하는 OpenAI SDK의 공식 채팅 API를 호출한다.
  - `None`인 생성 옵션은 요청에 포함하지 않는다.
  - SDK 응답 텍스트가 없으면 빈 문자열을 사용해 `ChatResponse`를 반환한다.
  - SDK 예외는 wrapping 없이 그대로 전파한다.
- `app/llms/__init__.py`에서 `OpenAIClient`를 export한다.
- 기존 Core Contract, Harness, Workflow, Skill, Evaluator, Generator, `MockLLMClient`는 변경하지 않는다.

## Test Plan

- `tests/test_openai_client.py`에서 Fake AsyncOpenAI 구현체로 네트워크 없이 검증한다.
- Fake는 요청으로 전달된 모델, 메시지, 생성 옵션을 기록하고, 구성된 응답 또는 예외를 반환한다.
- 메시지/설정 매핑, 응답 텍스트 매핑, 빈 텍스트 처리, 예외 전파, Protocol 사용을 검증한다.
- `UV_CACHE_DIR=.uv-cache uv run pytest`를 실행한다.

## Success Criteria

- `OpenAIClient`가 `LLMClient` 계약을 구현한다.
- SDK 인스턴스와 모델명은 생성자 주입으로 받는다.
- `ChatMessage`와 `GenerationConfig`가 OpenAI 요청으로 올바르게 매핑된다.
- OpenAI SDK 응답 텍스트가 `ChatResponse.content`로 반환된다.
- `config=None`도 정상 동작한다.
- OpenAI SDK 의존성은 `app/llms/openai.py`에 한정된다.
- 기존 구현을 변경하지 않고 전체 테스트가 통과한다.

## Assumptions

- OpenAI SDK는 `AsyncOpenAI`를 사용한다.
- Chat Completions나 Responses API 같은 SDK의 구체 API는 `OpenAIClient` 내부 구현 세부사항이며 `LLMClient` 계약에 포함하지 않는다.
- `GenerationConfig`는 Provider 독립 옵션만 가지며, SDK API에 맞는 파라미터명으로 매핑한다.
- Provider 원본 응답은 저장하지 않고 `ChatResponse.content`만 반환한다.
- SDK 의존성 분리는 구현 규칙으로 관리하며 별도 단위 테스트로 검사하지 않는다.

## Out of Scope

- Prompt Builder, Structured Output, Streaming, Tool Calling
- Retry, timeout, logging, exception wrapping, guardrail
- Model routing, ClaudeClient, GeminiClient, Business Logic

## Commit Message

```text
feat: implement openai llm client
```
