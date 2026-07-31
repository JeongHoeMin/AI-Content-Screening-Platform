# PR-39 — Secret-Safe Operational Logging v1

## 목표

Phase 9의 secret 관리 요구에 따라 실행·설정 오류가 로그에 raw exception 문자열 또는 API key를 남기지 않도록 한다. 사용자의 입력/설정 오류 분류는 유지하되, 민감한 문자열은 operational log boundary를 넘지 않는다.

## 범위

- `OpenAIConfig`의 explicit safe `repr`를 추가해 API key를 redaction한다.
- CLI input/config/execution error log에서 raw `str(error)` field를 제거하고 bounded error type만 기록한다.
- configuration precedence/validation/CLI exit code는 유지한다.
- redaction과 CLI logging field 회귀를 테스트한다.

## 비범위

- secret manager/KMS/Vault integration, key rotation, OS keychain, external notification credentials, audit encryption, provider usage/cost budget은 후속 작업이다.
- SDK request 또는 provider response의 이미 존재하는 contract를 바꾸지 않는다.

## 설계 결정

1. API key는 config 객체의 repr/로그에 절대 포함하지 않고 `[redacted]` marker만 보인다.
2. CLI는 correlation 가능한 `error_type`만 structured log에 기록한다. raw exception message는 article text·path·provider detail을 포함할 수 있어 사용하지 않는다.
3. user-facing process exit semantics는 그대로다. 구체 diagnosis는 trusted local development에서 exception chaining/test로 확인한다.

## 변경 이력

- 2026-07-30: 최초 계획 작성. project-wide logging 원칙에 맞춰 CLI가 남긴 unbounded error string을 제거한다.
