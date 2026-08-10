# 개발 가이드

## 작업 시작

작업 전 [PROJECT_GUIDE.md](PROJECT_GUIDE.md)를 읽고, 변경 성격에 맞는 `docs/` 가이드를 확인한다. 작업 계획은 별도의 `docs/` 계획 문서를 새로 작성하지 않고, `tasks/<작업 ID>/task.yaml`의 `requirements.items`와 `plan.steps`에 기록한다(`AGENTS.md` 참고). 구현 중 리뷰로 결정이 바뀌면 같은 `task.yaml`에 시간순으로 변경 이유, 결정, 범위 제한을 추가 기록한다.

## 코드 규칙

- 모든 Python 함수, 메서드, 변수, 반환값에 명확한 type hint를 작성한다.
- 외부 입력, 설정, DTO, Domain 모델은 Pydantic으로 표현한다.
- Domain 값은 immutable을 기본으로 하고 외부 API/CLI/Workflow를 알지 않게 한다.
- `print`는 사용하지 않고 로그는 `structlog`만 사용한다.
- 새 기능은 interface, deterministic/mock 구현, production adapter, Policy/Parser, 테스트의 책임을 분리한다.
- 기존 동작과 무관한 dirty worktree 변경은 수정하거나 되돌리지 않는다.

## 책임 배치

| 관심사 | 배치 위치 |
| --- | --- |
| 공통 request/result/error/metadata | `app/core/` |
| 외부 수집 및 provider registry | `app/providers/` |
| 외부 응답 adapter/LLM gateway | `app/llms/` |
| PromptBuilder | `app/prompts/` |
| prompt 문자열과 표현 | `app/prompt_templates/` |
| transport→Domain 검증 | 기능별 `parser.py`, `default_parser.py` |
| 최종 상태/점수/추천 | 기능별 `policy.py`, strategy |
| 실행 흐름과 상태 전달 | `app/workflows/`, `app/harness/` |
| executable 의존성 조립 | `app/bootstrap.py` |

Parser는 LLM, DB, Policy를 호출하지 않는다. Policy는 Prompt나 OpenAI를 호출하지 않는다. Skill은 상태를 변경하지 않고 Agent는 Skill만 호출한다. Harness/Workflow만 실행 상태와 I/O 연결을 관리한다.

## 변경 절차

1. 기존 interface, Domain 모델, Policy, Workflow 소비 지점을 읽어 계약을 파악한다.
2. 하위 호환이 필요한 public JSON/CLI/Mock 계약을 명시한다.
3. `task.yaml`의 `plan.steps`와 Parser/Policy 테스트를 먼저 또는 함께 갱신한다.
4. 구현은 dependency injection을 사용하고 bootstrap에서 조립한다.
5. recover 가능한 item 실패와 fatal 실행 실패를 구분한다.
6. 관련 단위·통합·회귀 테스트와 `git diff --check`를 실행한다.

## 보안과 로깅

로그에는 correlation에 필요한 제한된 식별자와 error kind만 기록한다. 기사 원문, prompt, API key, 개인정보, raw SDK response, 무제한 exception string은 기록하지 않는다. 외부 요청에 내부 candidate ID와 workflow state를 보내지 않는다.

## 체크리스트

코드 변경 전후로 다음을 확인한다.

- 새 Python 코드에 type hint가 빠진 곳은 없는가?
- 외부 입력 또는 구조화 데이터에 Pydantic 모델을 사용했는가?
- `print`가 추가되지 않았는가?
- 로깅이 필요하다면 `structlog`를 사용했는가?
- 새 프롬프트가 `app/prompt_templates/`에 저장되고 PromptBuilder가 `app/prompts/`에 있는가?
- Skill이 하나의 책임만 가지고 있는가?
- Agent가 Skill 외의 실행 단위를 직접 호출하지 않는가?
- 상태 변경이 Harness 밖에서 발생하지 않는가?

## 문서 유지

`docs/` 문서는 반복 참조하는 안정적인 운영 규칙을 담는다. 작업 단위 계획과 수정 이력은 새로운 `docs/pr-*.md`를 작성하지 않고 `tasks/<작업 ID>/task.yaml`에 남긴다. 기존 `docs/pr-*.md`는 과거 구현 기록으로 유지한다. 코드와 문서의 현재 상태가 다르면 코드를 기준으로 조용히 문서를 덮어쓰지 말고 차이를 확인해 함께 갱신한다.
