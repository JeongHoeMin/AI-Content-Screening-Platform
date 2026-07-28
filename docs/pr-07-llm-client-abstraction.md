# PR #7 LLMClient 추상화 도입 계획

## Summary

- `app/llms` 패키지를 추가해 채팅 기반 LLM 호출 공통 추상화 계층을 도입한다.
- LLM 입력은 `list[ChatMessage]`로 정의하고, `ChatMessage.role`은 `ChatRole(Enum)`을 사용한다.
- 생성 옵션은 `GenerationConfig`로 받되 Provider 독립적인 생성 옵션만 포함한다.
- LLM 응답은 `ChatResponse` 모델로 반환한다.
- `ChatResponse`는 LLM 응답 본문(`content`)만 표현한다.
- Provider 원본 응답은 실제 Provider 구현(PR #8 이후)에서 필요성이 확인되면 추가한다.
- 메서드명은 채팅 호출 의미가 명확한 `chat()`을 사용한다.
- LLM 도메인 모델은 검증보다 데이터 표현이 목적이므로 `pydantic.dataclasses.dataclass` 대신 표준 `dataclasses.dataclass`를 사용한다.

## Responsibilities

- `LLMClient`는 `ChatMessage` 목록을 입력받아 `ChatResponse`를 반환하고, 모델별 구현 차이를 숨긴다.
- `GenerationConfig`는 Provider와 무관한 생성 옵션만 표현하며 모델 선택을 담당하지 않는다.
- `ChatResponse`는 LLM 응답을 표현하는 도메인 모델이다.
- `ChatResponse`는 비즈니스 로직이 사용할 추상화된 응답 본문만 표현한다.
- Provider별 원본 응답은 이번 PR의 범위에 포함하지 않는다.
- LLM 도메인 모델은 순수 데이터 표현만 담당한다.
- Validation, Serialization 등은 도메인 모델의 책임이 아니다.
- Validation이 필요한 경우 이후 별도의 Pydantic 모델에서 담당한다.
- Prompt 생성, Response Parsing, Structured Output, Retry, Guardrail, Tool Calling, Business Logic은 이번 PR에서 구현하지 않는다.

## Implementation Changes

- `app/llms/models.py`를 추가한다.
  - 모든 도메인 모델은 표준 `dataclasses.dataclass`를 사용한다.
  - `pydantic.dataclasses.dataclass`는 사용하지 않는다.
  - `ChatRole(str, Enum)`:
    - `SYSTEM = "system"`
    - `USER = "user"`
    - `ASSISTANT = "assistant"`
  - `ChatMessage`:
    - `@dataclass(frozen=True)`
    - `role: ChatRole`
    - `content: str`
  - `GenerationConfig`:
    - `@dataclass(frozen=True)`
    - `temperature: float | None = None`
    - `max_tokens: int | None = None`
  - `ChatResponse`:
    - `@dataclass(frozen=True)`
    - `content: str`
    - `raw: object | None = None`
  - `TOOL`, `FUNCTION`, `DEVELOPER` role은 v1에 추가하지 않는다.
  - `GenerationConfig`에 `model`은 포함하지 않는다.
- `app/llms/base.py`를 추가한다.
  - `LLMClient(Protocol)`:
    ```python
    async def chat(
        self,
        messages: list[ChatMessage],
        config: GenerationConfig | None = None,
    ) -> ChatResponse:
        ...
    ```
  - Streaming, Tool Calling, Structured Output, Model Routing은 포함하지 않는다.
- `app/llms/mock.py`를 추가한다.
  - `MockLLMClient(LLMClient)` 구현
  - stateless로 유지하고 입력 messages/config를 저장하지 않는다.
  - `config`는 무시한다.
  - 항상 `ChatResponse(content="Mock Response")`를 반환한다.
  - 예외 처리는 구현하지 않고 항상 성공한다.
- `app/llms/__init__.py`에서 `ChatRole`, `ChatMessage`, `GenerationConfig`, `ChatResponse`, `LLMClient`, `MockLLMClient`를 export한다.
- 기존 Core Contract, Harness, Workflow, Evaluator, Generator, Skill 구현은 변경하지 않는다.

## Test Plan

- `tests/test_mock_llm_client.py`를 추가한다.
- `ChatRole.SYSTEM`, `ChatRole.USER`, `ChatRole.ASSISTANT` 값이 올바른지 검증한다.
- `ChatMessage(role=ChatRole.USER, content="Hello")`가 정상 생성되는지 검증한다.
- `GenerationConfig()`가 기본값으로 정상 생성되는지 검증한다.
- `GenerationConfig`에 `temperature`, `max_tokens`가 올바르게 저장되는지 검증한다.
- `GenerationConfig`는 모델 정보를 가지지 않는 것을 확인한다.
- `ChatResponse(content="Mock Response")`가 정상 생성되는지 검증한다.
- `MockLLMClient.chat(...)`가 `ChatResponse`를 반환하는지 검증한다.
- `ChatResponse.content`가 예상 mock 문자열과 일치하는지 검증한다.
- `config=None`과 `GenerationConfig()` 모두 정상 동작하며 동일한 `ChatResponse`를 반환하는지 검증한다.
- `client: LLMClient = MockLLMClient()` 형태로 Protocol 계약 사용이 가능한지 확인한다.
- 동일한 입력에 여러 번 호출해도 동일한 응답을 반환해 stateless 동작을 검증한다.
- OpenAI, Anthropic, Gemini SDK 의존성이 추가되지 않았는지 변경 범위로 확인한다.
- 최종 검증은 `uv run pytest`로 수행한다.

## Success Criteria

- `app/llms` 패키지와 `models.py`, `base.py`, `mock.py`가 추가된다.
- `ChatRole`, `ChatMessage`, `GenerationConfig`, `ChatResponse`, `LLMClient`, `MockLLMClient`가 추가된다.
- `ChatMessage.role`은 `ChatRole` 타입을 사용한다.
- `LLMClient.chat()`은 `list[ChatMessage]`와 Optional `GenerationConfig`를 입력받고 `ChatResponse`를 반환한다.
- `ChatResponse`는 `content`만 가진다.
- Provider 원본 응답은 이번 PR에 포함하지 않는다.
- `ChatMessage`, `GenerationConfig`, `ChatResponse`는 표준 `dataclasses.dataclass`를 사용한다.
- LLM 도메인 모델은 Pydantic에 의존하지 않는다.
- `GenerationConfig`는 Provider 독립적인 생성 옵션만 포함하고 모델 정보를 포함하지 않는다.
- 모델 선택은 `LLMClient` 구현체의 책임이다.
- `MockLLMClient`는 `GenerationConfig`를 받아도 동일한 `ChatResponse`를 반환한다.
- `MockLLMClient`는 stateless로 구현된다.
- 실제 LLM SDK 의존성이 추가되지 않는다.
- Prompt Builder, Response Parsing, Structured Output, Streaming, Tool Calling, Retry, Guardrail은 구현되지 않는다.
- 기존 Core Contract, Harness, Workflow, Evaluator, Generator, Skill 구현은 변경되지 않는다.
- 모든 테스트가 통과하고 `uv run pytest`가 성공한다.

## Assumptions

- `ChatMessage`는 v1에서 `role`, `content`만 가진다.
- `ChatRole`은 v1에서 `SYSTEM`, `USER`, `ASSISTANT`만 지원한다.
- `GenerationConfig`는 Provider 독립적인 생성 옵션만 가진다.
- 모델 선택은 `LLMClient` 구현체의 생성자 또는 설정에서 관리한다.
- `GenerationConfig`의 모든 필드는 v1에서 Optional로 유지한다.
- `ChatResponse`는 v1에서 `content`만 가진다.
- Provider 원본 응답은 실제 Provider 구현 단계에서 필요성이 확인되면 추가한다.
- Mock 응답은 `ChatResponse(content="Mock Response")`로 고정한다.
- LLM 도메인 모델은 순수 도메인 모델로 유지한다.
- Validation은 이후 별도의 계층에서 처리한다.
- 이번 PR의 커밋 메시지는 `feat: introduce llm client abstraction`을 사용한다.

## Change Log

### 2026-07-29

- LLM 도메인 모델은 검증보다 순수 데이터 표현이 목적이므로 `pydantic.dataclasses.dataclass` 대신 표준 `dataclasses.dataclass`를 사용하기로 결정했다.
- `ChatResponse.raw`는 실제 Provider 구현 전까지 필요성이 검증되지 않은 필드이므로 v1 범위에서 제거했다.
- Provider 원본 응답 보관은 PR #8 이후 실제 Provider 구현 단계에서 필요성이 확인되면 다시 설계한다.
