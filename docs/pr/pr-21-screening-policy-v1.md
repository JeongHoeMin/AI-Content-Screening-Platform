# PR #21 Screening Policy v1

## 목표

뉴스 이벤트 추출 뒤의 첫 AI 심사 정책을 추가한다. 각 추출 이벤트를 수락·검토·거절로 기록하지만,
기존 Resolver, Analyzer, Aggregator, Scorer, Recommendation 파이프라인은 변경하지 않는다.

## 평가와 결정 경계

LLM은 관련성, 중요도, 신뢰도, 교차 검증 필요 여부, 사람이 읽을 수 있는 이유로 구성된
`ScreeningAssessment`만 반환하며 최종 결정은 반환하지 않는다.

`ScreeningPolicy`가 모든 `ACCEPT`, `REVIEW`, `REJECT` 결정을 소유한다. 기본 정책은 다음 고정 순서다.

1. 관련성 또는 중요도가 40 미만이면 거절한다.
2. 교차 검증이 필요하면 검토한다.
3. 관련성·중요도·신뢰도가 모두 70 이상이면 수락한다.
4. 나머지는 검토한다.

불변 `ScreeningPolicyConfig`에 임계값을 두므로 알고리즘 변경 없이 의존성 설정으로 조정한다.
`reject_relevance_below=40`은 0~39를 거절하고, `accept_relevance_at_least=70`은
70~100이 수락 조건을 만족하게 한다. 중요도와 신뢰도에도 동일한 경계 의미를 적용한다.
교차 검증 검토는 거절 뒤·수락 전에 평가하므로 거절을 되돌리지는 않지만 무검토 수락을 막는다.

## Workflow 경계

비공개 그래프는 `Extract -> Screen Events -> Resolve`를 실행한다. Node는 새 상태 필드만 반환하고
입력 상태를 변경하지 않는다. 심사 결정은 추출 시 생성된 동일한 `NewsEvent` 인스턴스를 보존한다.
v1의 `ScreeningDecision`은 원본 이벤트 전체를 유지하며 인위적인 `event_id` 시스템은 추가하지 않는다.

이번 PR에서 결정은 관측값이다. `REJECT`도 이벤트를 제거하거나 이후 결정적 도메인 처리를 바꾸지 않는다.
`ScreeningResult`는 Recommendation 결과와 별도로 결정을 반환한다. 수락·검토·거절 통계 합은 항상 결정 수와 같다.

## LLM과 파싱 경계

`EventScreener`는 프롬프트가 원문 기사 맥락을 보존하도록 기사 단위 추론 스냅샷을 받는다.
내부에서 후보를 batch로 나누고 PromptBuilder에 프롬프트 생성을 위임하며
`StructuredOutputLLM`에서 타입이 지정된 Pydantic 출력만 받는다.

Parser는 누락·알 수 없음·중복·불일치 candidate ID를 검증하고 정책 평가 전 원래 이벤트 순서를 복원한다.
대체 `NewsEvent` 객체는 만들지 않는다. 빈 이벤트 입력은 LLM 호출을 생략한다.
`candidate_id`는 하나의 구조화 LLM 평가를 입력 후보에 연결하는 요청 지역 상관관계 키이며 영속 이벤트 ID가 아니다.
프롬프트는 private chain-of-thought가 아닌 간결한 사용자용 이유를 요청하며, 이유는 1~3개로 제한한다.

## 후속 보완과 범위 제한

설정 이름은 비교 의미를 직접 드러낸다. `*_below`는 엄격한 거절 비교, `*_at_least`는 포괄적 수락 비교에 사용한다.
이번 PR은 교차 검증, 웹 검색, 이벤트 필터링·순위화, 추천 정책 변경, retry, 부분 성공, batch 실행 메타데이터 확장을 하지 않는다.
이후 작업은 Assessment-to-Policy 책임 경계를 유지한 채 교차 검증, 복구 정책, 결정 기반 downstream routing을 추가할 수 있다.
