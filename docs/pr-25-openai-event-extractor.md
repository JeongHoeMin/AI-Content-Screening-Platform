# PR-25 OpenAI 이벤트 추출기

## 요약

`openai` 실행 모드는 이벤트 추출에만 OpenAI Responses API structured-output adapter를 사용한다.
심사, 교차 검증, 해소, 분석, 점수화, 추천은 결정적 Mock/Rule 구현을 유지한다.

## 설정과 실행

필수 환경 변수는 다음과 같다.

```text
OPENAI_API_KEY
```

선택 환경 변수와 기본값은 다음과 같다.

```text
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=2
```

OpenAI 모드는 repository root의 `.env`가 있으면 자동으로 읽고, shell 환경 변수는 `.env`보다 우선한다.
`OPENAI_MODEL`은 trim 후 비어 있으면 안 되며 `OPENAI_TIMEOUT_SECONDS`는 유한한 양수,
`OPENAI_MAX_RETRIES`는 음이 아닌 정수여야 한다.

```bash
OPENAI_API_KEY="..." uv run screening \
  --mode openai \
  --input examples/openai-articles.json
```

## 구조

OpenAI adapter는 system prompt, user prompt, Pydantic response model과 함께
`AsyncOpenAI.responses.parse`를 호출한다. 완료된 응답을 확인한 뒤 `output_parsed`만 반환하며
OpenAI SDK 응답 타입은 adapter 밖으로 나가지 않는다. 공통 structured-output 예외는
`app/llms/errors.py`에 두어 일반 추출 오케스트레이션이 OpenAI adapter 모듈에 의존하지 않게 한다.
예상 가능한 SDK 요청·응답 처리 실패만 복구 가능하며 예상 밖 프로그래밍 오류는 batch 실패로 변환하지 않는다.

PromptBuilder는 메시지를 조립하고 template은 명시적 Article ID/Source/Title/Published at/Content 필드를 표현하며,
Parser는 타입이 지정된 응답 데이터를 도메인 이벤트로 변환한다. 기사 본문은 지시가 아닌 신뢰할 수 없는 데이터다.
Parser는 공백을 정리하고 빈 값을 제거하며 company·industry·keyword는 대소문자 무시로 중복 제거하되 첫 표기를 보존한다.
reason은 정규화된 정확한 텍스트 기준으로 중복 제거한다. `confidence`는 이벤트의 사실 진위가 아니라 모델의 추출 확신도다.

## 실패 정책

- 잘못된 개별 이벤트는 제외하고 복구 가능한 오류로 기록한다.
- API 오류는 안전한 SDK 오류 타입과 함께 해당 batch만 제외한다.
- 응답 실패는 `response_failed`, `response_incomplete`, `unknown_response_status:<status>`,
  `refusal`, `missing_parsed_output`으로 기록한다.
- 전체 응답 파싱 실패는 해당 batch만 제외한다.
- 완료된 batch의 `events=[]`는 성공이다.
- 하나 이상의 batch가 완료되면 workflow를 계속하고, 모든 시도 batch가 실패한 경우에만 실행 오류를 발생시킨다.

## 테스트 전략과 범위 제외

단위 테스트는 fake SDK client를 사용하며 자동 테스트가 OpenAI 서비스를 호출하지 않는다.
OpenAI screener·validator, 기사 수집·크롤링, 웹 검색, RAG, 영속화, 스케줄링, UI, 이벤트 clustering,
ticker 추론, prompt versioning, 비용 추적은 제외한다.
