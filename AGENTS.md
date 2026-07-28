# Codex Project Guidelines

이 프로젝트는 Codex만 사용하여 개발한다. 모든 코드 변경은 아래 규칙을 우선 적용한다.

## Core Rules

- Python 코드는 모든 함수, 메서드, 변수, 반환값에 명확한 type hint를 작성한다.
- 데이터 검증, 입출력 스키마, 설정 모델, 도메인 모델에는 Pydantic을 사용한다.
- `print` 사용은 금지한다.
- 로깅은 `structlog`를 사용한다.
- 프롬프트는 코드에 직접 작성하지 않고 `prompts/` 폴더에 저장한다.
- Skill은 하나의 책임만 가진다.
- Agent는 Skill만 호출한다.
- Harness만 상태를 변경한다.

## Architecture Boundaries

### Skill

- 하나의 Skill은 하나의 명확한 작업만 수행한다.
- Skill은 상태를 직접 변경하지 않는다.
- Skill은 다른 Skill의 내부 구현에 의존하지 않는다.
- Skill 입력과 출력은 가능하면 Pydantic 모델로 표현한다.

### Agent

- Agent는 의사결정과 오케스트레이션만 담당한다.
- Agent는 외부 API, 데이터베이스, 파일 시스템, 상태 저장소를 직접 변경하지 않는다.
- Agent는 필요한 작업을 Skill 호출로만 수행한다.
- Agent가 사용하는 프롬프트는 반드시 `prompts/`에서 로드한다.

### Harness

- Harness는 실행 흐름, 상태 변경, 입출력 연결을 담당한다.
- 상태 생성, 갱신, 저장, 복구는 Harness에서만 수행한다.
- Harness는 Agent와 Skill의 실행 결과를 검증 가능한 방식으로 기록한다.

## Prompt Management

- 모든 프롬프트 파일은 `prompts/` 하위에 둔다.
- 프롬프트 파일명은 역할과 목적이 드러나도록 작성한다.
- 코드 안에는 프롬프트 본문을 인라인 문자열로 길게 작성하지 않는다.
- 프롬프트 변경은 코드 변경과 동일하게 리뷰 가능한 단위로 관리한다.

## Logging

- 모든 로그는 `structlog`를 통해 남긴다.
- 사용자 출력, 디버깅, 테스트 확인 목적으로도 `print`를 사용하지 않는다.
- 로그에는 추적 가능한 컨텍스트를 포함하되 민감한 정보는 기록하지 않는다.

## Implementation Checklist

코드 변경 전후로 다음을 확인한다.

- 새 Python 코드에 type hint가 빠진 곳은 없는가?
- 외부 입력 또는 구조화 데이터에 Pydantic 모델을 사용했는가?
- `print`가 추가되지 않았는가?
- 로깅이 필요하다면 `structlog`를 사용했는가?
- 새 프롬프트가 `prompts/`에 저장되었는가?
- Skill이 하나의 책임만 가지고 있는가?
- Agent가 Skill 외의 실행 단위를 직접 호출하지 않는가?
- 상태 변경이 Harness 밖에서 발생하지 않는가?
