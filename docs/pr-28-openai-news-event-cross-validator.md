# PR-28 OpenAI 뉴스 이벤트 교차 검증기

## 요약

OpenAI 모드에서 이벤트 추출과 심사 다음에 OpenAI 기반 교차 검증을 실행한다.
LLM은 비교 기사별 근거 관계만 평가하고 Parser가 도메인 변환과 부분 실패를 처리하며
Policy가 최종 교차 검증 상태를 결정한다. Mock 모드와 CLI JSON schema는 유지한다.

## 계약과 실패 정책

LLM 응답은 batch-local `event_index`와 `evidence_index`를 사용하며 내부 candidate ID나
workflow 상태를 노출하지 않는다. 잘못된 event는 정상 sibling을, 잘못된 evidence는 정상 evidence를
버리지 않는다. Provider 호출, structured-output 응답 실패, 잘못된 응답 root만 batch-level 실패다.
입력 대상이 있으나 유효 결과가 없으면 `NoValidCrossValidationResultsError`를 발생시킨다.

오류 로그에는 index, 내부 candidate ID, article ID, 제한된 오류 종류만 기록한다. 기사 본문,
prompt, 원시 응답, API key는 기록하지 않는다.

## 독립 출처와 조립

독립 출처는 LLM이 판단하지 않는다. Policy는 URL domain 또는 source가 같은 기사를 동일 출처로 보고,
그 일치 관계의 연결 요소를 하나의 출처 그룹으로 계산한다. URL domain은 소문자화, port 제거,
선행 `www.` 제거까지만 수행하며 Public Suffix List 기반 등록 가능 도메인 추출은 후속 범위다.

OpenAI Extractor, Screener, `LLMEventCrossValidator`는 같은 stateless structured-output gateway를
공유한다. Mock mode는 `DeterministicMockCrossValidator`를 유지한다.

## 검증

`uv run pytest`, `uv run python -m compileall app tests`, `git diff --check`를 실행한다.
실제 smoke test에서는 같은 사건의 독립 보도가 supports, 상충 기사가 conflicts, 관계없는 기사가
unrelated로 평가되는지와 투자 조언·prompt injection 비추종을 확인한다.
