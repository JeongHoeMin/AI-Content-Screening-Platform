# PR #2 핵심 계약 예외와 정규화 메타데이터

## 요약

- 프로젝트 전용 예외와 명시적 Skill 단계를 포함하도록 핵심 계약 v1을 보완한다.
- Registry 조회에서 일반 `KeyError`를 노출하지 않는다.
- Normalizer를 비동기 계약으로 전환하고 `normalize_error_count` 의미를 명확히 한다.

## 주요 변경

- `app/core/exceptions`에 `SkillExecutionError`, `AllProvidersFailedError`,
  `ProviderNotFoundError`, `NormalizerNotFoundError`를 추가한다.
- 현재 사용 단계만 포함하는 `SkillStage`를 도입한다.
  - `PROVIDER_COLLECT`, `NORMALIZE`
- `SkillError.stage`는 문자열 대신 `SkillStage`를 사용한다.
- `CommunityNormalizer.normalize()`를 비동기로 변경하고
  `ProviderResultMetadata.normalize_error_count`를 추가한다.
- `ProviderExecution`은 slot dataclass로 표현한다.

## 설계 규칙

- 복구 가능한 실패는 `SkillError`, 복구 불가능한 실패는 프로젝트 전용 예외로 표현한다.
- 복구 가능한 registry 조회 실패는 오류로 기록한다.
- `normalize_error_count`는 `RawPost`에서 `Post`로 변환하는 실패만 센다.
- Normalizer registry 조회 실패는 `errors`에 기록하되 `normalize_error_count`에는 포함하지 않는다.
- Python 3.9 호환성을 위해 `SkillStage`는 `class SkillStage(str, Enum)`을 유지한다.

## 테스트 계획 및 범위 제외

- 누락 Provider·Normalizer의 전용 예외, 전체 Provider 실패, 비동기 Normalizer 대기,
  정규화 오류 집계를 검증한다.
- 예외·단계 정리 외의 핵심 계약 기능, Resolver, Harness 변경, 실제 Provider 연동은 제외한다.
