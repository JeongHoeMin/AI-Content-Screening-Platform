# Codex Project Guidelines

이 프로젝트는 Codex만 사용하여 개발한다. 모든 코드 변경은 아래 규칙을 우선 적용한다.

## Core Rules

- Python 코드는 모든 함수, 메서드, 변수, 반환값에 명확한 type hint를 작성한다.
- 데이터 검증, 입출력 스키마, 설정 모델, 도메인 모델에는 Pydantic을 사용한다.
- `print` 사용은 금지한다.
- 로깅은 `structlog`를 사용한다.
- 프롬프트 조립 코드는 `app/prompts/`에, 프롬프트 문자열과 표현 로직은 `app/prompt_templates/`에 둔다.
- Skill은 하나의 책임만 가진다.
- Agent는 Skill만 호출한다.
- Harness만 상태를 변경한다.

## Architecture Boundaries

### Skill

- 하나의 Skill은 하나의 명확한 작업만 수행한다.
- Skill은 상태를 직접 변경하지 않는다.
- Skill은 다른 Skill의 내부 구현에 의존하지 않는다.
- Skill 입력과 출력은 가능하면 Pydantic 모델로 표현한다.
- 모든 Skill은 공통 인터페이스 `async execute(request) -> result`를 따른다.
- Skill은 Harness, LangGraph, CLI, API 같은 실행 환경을 알지 않는다.
- Skill은 자신의 책임 범위 안에서 필요한 Service를 사용할 수 있지만, 직접 생성하지 않고 외부에서 의존성으로 주입받는다.
- Recover 가능한 실패는 Exception 제어 흐름으로 표현하지 않고 Result의 error 관측값으로 반환한다.
- Recover 불가능한 실패만 Exception으로 처리한다.
- Skill은 "판단"이 아니라 자신의 책임 범위에서 관측한 사실을 반환한다.

### Agent

- Agent는 의사결정과 오케스트레이션만 담당한다.
- Agent는 외부 API, 데이터베이스, 파일 시스템, 상태 저장소를 직접 변경하지 않는다.
- Agent는 필요한 작업을 Skill 호출로만 수행한다.
- Agent가 사용하는 프롬프트는 반드시 `app/prompts/`의 PromptBuilder를 통해 생성한다.

### Harness

- Harness는 실행 흐름, 상태 변경, 입출력 연결을 담당한다.
- 상태 생성, 갱신, 저장, 복구는 Harness에서만 수행한다.
- Harness는 Agent와 Skill의 실행 결과를 검증 가능한 방식으로 기록한다.
- Harness는 Skill Result의 metadata와 errors를 기반으로 retry, ignore, fallback 같은 제어 결정을 내린다.

## Core Contract

- 프로젝트 전체 Skill 계약은 `app/core/`에 둔다.
- `SkillRequest`는 모든 Skill request 모델의 공통 base로 사용한다.
- `SkillResult`는 `data`, `metadata`, `errors`를 포함한다.
- `SkillMetadata`는 `started_at`, `finished_at`, `duration_seconds` 같은 공통 실행 관측값을 포함한다.
- Skill별 metadata는 `SkillMetadata`를 상속하거나 generic metadata 타입으로 확장한다.
- `SkillError`는 recover 가능한 실패를 표현하는 공통 관측 모델로 사용한다.
- Skill Result는 비즈니스 데이터와 실행 메타데이터를 분리한다.

## Community Collection Architecture

- 게시글 수집은 `Provider -> RawPost -> Normalizer -> NormalizeResult -> Post` 흐름을 따른다.
- Provider는 원본 데이터 수집만 담당한다.
- Provider는 공통 `Post`를 직접 만들지 않고 community별 `RawPost` 모델을 반환한다.
- `RawPost`는 단순 `payload` dict가 아니라 community별 Pydantic 도메인 모델로 정의한다.
- Normalizer는 community별 `RawPost`를 공통 `Post`로 변환한다.
- Normalizer는 `Post`를 직접 반환하지 않고 `NormalizeResult`를 반환한다.
- `NormalizeResult`는 `post` 또는 recover 가능한 `error`를 담는다.
- CollectPostsSkill은 Provider와 Normalizer 선택 로직을 직접 가지지 않고 Registry 조회만 사용한다.
- v1에서는 Resolver를 만들지 않는다. 하나의 `CommunityType`에 여러 Provider 후보가 필요해질 때 v2에서 도입한다.
- `ProviderRegistry`는 `CommunityType -> CommunityProvider` 매핑을 관리한다.
- `NormalizerRegistry`는 `CommunityType -> CommunityNormalizer` 매핑을 관리한다.
- 신규 Community 추가는 Provider, Normalizer, Registry 등록만으로 가능해야 하며 Skill 내부 조건문을 수정하지 않는다.

## CollectPostsSkill Rules

- CollectPostsSkill은 게시글 수집과 정규화된 관측 결과 반환만 담당한다.
- CollectPostsSkill은 AI 판단, LLM 호출, Prompt 사용, DB 저장, Cache 저장, 정렬 정책, 중복 제거, 광고 판별을 하지 않는다.
- CollectPostsSkill은 Provider를 병렬 실행한다.
- Provider 하나가 실패해도 다른 Provider 실행은 계속한다.
- Provider 실패, Normalizer 실패, Timeout 등 recover 가능한 실패는 Result errors에 기록한다.
- 전체 Provider가 실패한 경우에만 Exception을 발생시킨다.
- `sources`는 문자열이 아니라 `CommunityType` enum을 사용한다.
- `period`는 문자열이 아니라 `timedelta` 또는 datetime 기반 모델을 사용한다.

## Prompt Management

- PromptBuilder 코드는 `app/prompts/` 하위에 둔다.
- 프롬프트 문자열과 표현 로직은 `app/prompt_templates/` 하위의 Python 상수와 함수로 관리한다.
- PromptBuilder는 입력 DTO를 `ChatMessage`로 조립만 하고 문자열 치환이나 데이터 표현을 직접 수행하지 않는다.
- PromptTemplate은 템플릿 치환과 JSON, YAML, Markdown 같은 Prompt 표현 방식을 담당한다.
- PromptBuilder 입력 DTO는 내부 계층 간 전달용 immutable 객체로 관리한다. 외부 경계 입력은 Pydantic으로 검증한다.
- 프롬프트 본문은 Evaluator, Generator, Skill 같은 비-PromptTemplate 코드에 인라인으로 작성하지 않는다.
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
- 새 프롬프트가 `app/prompt_templates/`에 저장되고 PromptBuilder가 `app/prompts/`에 있는가?
- Skill이 하나의 책임만 가지고 있는가?
- Agent가 Skill 외의 실행 단위를 직접 호출하지 않는가?
- 상태 변경이 Harness 밖에서 발생하지 않는가?

## Planning Documentation

- 승인된 개발 계획은 구현을 시작하기 전에 반드시 `docs/` 폴더에 Markdown 문서로 작성한다.
- 계획 문서는 PR 또는 작업 단위별로 분리한다.
- 문서 파일명은 작업 순서와 목적이 드러나도록 작성한다.
- 구현 중 리뷰나 수정사항이 생기면 해당 계획 문서에 시간순으로 추가 기록한다.
- 수정사항 기록에는 변경 이유, 결정 내용, 범위 제한을 함께 남긴다.
- 구현은 최신 계획 문서에 기록된 내용과 일치해야 한다.
