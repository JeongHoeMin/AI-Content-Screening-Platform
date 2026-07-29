# PR #1 핵심 계약과 CollectPostsSkill

## 요약

- 기능별 Skill을 추가하기 전에 프로젝트 공통 핵심 Skill 계약을 도입한다.
- 이 계약 위의 첫 Skill로 `CollectPostsSkill`을 구현한다.
- Skill은 Provider에서 게시글을 수집하고 원본 게시글을 정규화해 사실 관측 결과를 반환한다.
- AI 판단, 중복 제거, 순위화, 저장, 프롬프트 사용은 수행하지 않는다.

## 주요 변경

- `app/core`에 다음을 정의한다.
  - `Skill`, `SkillRequest`, `SkillResult`, `SkillMetadata`, `SkillError`
- `app/models`에 `CommunityType`, `Post`, `RawPost`, `RawRedditPost`,
  `RawDcInsidePost`, `NormalizeResult` 및 CollectPosts 요청·데이터·메타데이터 모델을 정의한다.
- `app/providers`에 `CommunityProvider`, `CommunityNormalizer`,
  `ProviderRegistry`, `NormalizerRegistry`, mock Provider·Normalizer를 정의한다.
- `CollectPostsSkill`은 생성자 주입으로 registry를 받고 Provider를 병렬 실행하며,
  결과를 정규화해 `SkillResult[CollectPostsData, CollectPostsMetadata]`를 반환한다.

## 설계 규칙

- Skill 인터페이스는 `async execute(request) -> SkillResult`다.
- Skill은 공유 상태를 변경하지 않고 Harness가 상태 변경을 소유한다.
- Agent는 Skill만 호출한다.
- Provider는 원본 데이터를 수집하고 Normalizer는 이를 공통 도메인 모델로 변환한다.
- 새 Provider와 Normalizer는 Skill 내부 분기 대신 registry 등록으로 추가한다.

## 테스트 계획

- 핵심 계약 모델 검증과 Provider·Normalizer registry 조회를 검증한다.
- Provider 병렬 실행과 일부 Provider 실패 시 정상 Provider 계속 실행을 검증한다.
- 모든 Provider 실패는 복구 불가능 예외를 발생시킨다.
- Normalizer 실패는 복구 가능한 오류 메타데이터로 기록한다.

## 범위 제외

- 실제 Reddit/DCInside/Ruliweb 연동, LLM 호출, 프롬프트 사용, DB·캐시 저장, LangGraph 연동.
