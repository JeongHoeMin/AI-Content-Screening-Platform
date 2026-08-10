# PR-24 Executable Mock Bootstrap and CLI

## 목적

API 키와 네트워크 없이 Article JSON을 입력받아 Screening Workflow 전체를 실행한다.

## 계약

- Bootstrap은 `ExecutionMode` Enum만 받고 현재 `MOCK`만 지원한다.
- 성공 결과는 stdout의 순수 JSON이며 오류 로그는 stderr, 입력 오류는 exit 2, 실행 오류는 exit 1이다.
- mock grouping key는 Article title의 공백 정규화·casefold 값이다. mock은 assessment만 만들고 기존 Policy가 최종 상태를 결정한다.

## Mock 계약

- Extractor는 Event title과 summary를 Article에서 결정론적으로 유도한다. summary는 공백을 정규화한 `content`의 처음 500자다.
- 현재 Article 모델에는 회사·산업 metadata가 없으므로 Event `companies`와 `industries`는 비워 둔다. 이는 실제 추출 품질 모사가 아닌 Workflow 조립 검증의 제한이다.
- grouping은 연속 공백 collapse와 `casefold` 뒤 완전 일치한 title만 같은 그룹으로 취급한다. 구두점·어순·동의어는 정규화하지 않으며 semantic clustering이 아니다.
- Bootstrap은 `ExecutionMode → WorkflowFactory` registry를 사용한다. 현재 MOCK만 등록하며, 이후 OpenAI mode는 factory 추가로 확장한다. 매 호출은 새 Workflow와 의존성을 생성한다.

## 구현 중 보완 기록

- mock grouping helper를 production domain 모델과 분리된 `app.mock_grouping`으로 이동했다.

## 범위

OpenAI, 뉴스 수집, 환경변수 설정은 포함하지 않는다.
