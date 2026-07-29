# PR-24 Executable Mock Bootstrap and CLI

## 목적

API 키와 네트워크 없이 Article JSON을 입력받아 Screening Workflow 전체를 실행한다.

## 계약

- Bootstrap은 `ExecutionMode` Enum만 받고 현재 `MOCK`만 지원한다.
- 성공 결과는 stdout의 순수 JSON이며 오류 로그는 stderr, 입력 오류는 exit 2, 실행 오류는 exit 1이다.
- mock grouping key는 Article title의 공백 정규화·casefold 값이다. mock은 assessment만 만들고 기존 Policy가 최종 상태를 결정한다.

## 범위

OpenAI, 뉴스 수집, 환경변수 설정은 포함하지 않는다.
