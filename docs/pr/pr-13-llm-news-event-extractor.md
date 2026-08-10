# PR #13 LLM News Event Extractor 구현

## Summary

- PR #12의 Domain, Prompt와 Parser 계약을 실제 LLM 호출 경로로 연결한다.
- `NewsEventRequester`는 LLM 통신만 추상화하는 stateless Infrastructure
  Adapter다.
- `LLMNewsEventExtractor`는 PromptBuilder, Requester, Parser 호출만 조율한다.
- 새로운 비즈니스 로직이나 오류 처리 정책은 추가하지 않는다.

## Contracts and Responsibilities

### NewsEventRequester

- `request(messages: List[ChatMessage]) -> ChatResponse` 비동기 Protocol로 정의한다.
- Prompt를 생성하거나 메시지를 해석하지 않는다.
- 메시지 목록을 수정하거나 복사하지 않으며 입력 identity를 유지한다.
- 응답과 예외를 수정, wrapping 또는 변환하지 않는다.
- Parser와 Domain 모델을 알지 못한다.
- `LLMNewsEventRequester`는 LLMClient만 생성자 주입받는 stateless 구현체이며,
  `LLMClient.chat()`을 정확히 한 번 `config=None`으로 호출한다.

### LLMNewsEventExtractor

- `NewsEventRequester`, `NewsEventParser`,
  `PromptBuilder[NewsEventPromptInput]`을 생성자 주입받는다.
- Application Layer에서 PromptBuilder, Requester, Parser를 조율한다.
- 평가 결과로 PromptInput을 만든 뒤 PromptBuilder, Requester, Parser를 정확히
  이 순서로 한 번씩 호출한다.
- 각 계층의 반환 객체를 복사하지 않으며 Parser의 이벤트 목록을 그대로 반환한다.
- Prompt, JSON, DTO, Domain 생성이나 retry, timeout, logging, metrics,
  guardrail 및 투자 분석을 담당하지 않는다.
- 의존성의 예외를 그대로 전파하고 새로운 Exception을 정의하지 않는다.

## Test Plan

- Requester의 메시지·응답 identity, `config=None`, 단일 호출과 예외 전파를
  검증한다.
- Extractor의 Builder → Requester → Parser 호출 순서를 검증한다.
- 평가 결과, 메시지, 응답과 최종 이벤트 목록의 identity를 검증한다.
- 생성자 주입 시 호출이나 부수 효과가 없음을 검증한다.
- 각 단계 실패 시 이후 단계가 호출되지 않고 동일 예외가 전파되는지 검증한다.
- 기존 테스트를 포함한 전체 `pytest`, compile과 `git diff --check`를 실행한다.

## Assumptions and Roadmap

- Requester는 Application Service가 아닌 Infrastructure Adapter다.
- Extractor는 구체 Builder가 아닌 PromptBuilder Protocol에 의존한다.
- 동일 입력을 동일 forwarding 절차로 전달하지만 LLM 응답의 결정성을 보장하지
  않는다.
- Generation 설정은 이번 범위가 아니므로 `config=None`을 사용한다.
- PR #13 완료 후 생성되는 NewsEvent를 PR #14의 중복 제거 입력으로 사용한다.

## Change Log

### 2026-07-29

- Protocol의 Docstring에서 구현 세부인 LLMClient 호출 방식과 호출 횟수를 제거해
  forwarding 계약, identity 보존, 응답 반환 및 예외 전파만 표현하도록 정리했다.
- LLMNewsEventExtractor의 Application Layer 오케스트레이션 역할과 의도적으로
  수행하지 않는 책임을 Docstring에 명시했다. 동작은 변경하지 않았다.

## Commit Message

```text
feat: connect llm news event extractor
```
