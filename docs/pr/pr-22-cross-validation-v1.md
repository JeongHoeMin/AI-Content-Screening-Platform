# PR-22 Cross Validation v1

## 목적

`REVIEW` 이벤트를 현재 Workflow에 포함된 다른 기사와 비교해, 기사 간 주장 일치도를 구조화하여 기록한다. 외부 검색이나 downstream 정책 변경은 포함하지 않는다.

## 결정

- LLM은 관계 Assessment만 반환하며 Policy가 Evidence, 독립 출처 수, 최종 Status를 생성한다.
- Candidate는 Workflow node가 만들고 LLM adapter는 완성된 Candidate만 처리한다.
- Related Article이 없는 REVIEW는 LLM 호출 없이 Policy의 insufficient-evidence 경로로 결과를 만든다.
- 독립 출처 수는 SUPPORTS Article의 `source.strip().casefold()` 고유값 수다.
- Result confidence는 LLM 관계 분류 confidence이며 최종 Status 확률이 아니다.

## 구현 중 보완 기록

- Article별 claim 배정 계약은 v1에 없다. Assessment claim은 후보 전체 비교의 관측값이므로, 개별 `ValidationEvidence`에는 복사하지 않고 빈 tuple로 둔다. Article별 claim이 필요하면 후속 버전에서 article별 assessment 모델을 도입한다.
