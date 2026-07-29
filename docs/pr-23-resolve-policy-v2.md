# PR-23 Resolve Policy v2

## 목적

Screening 판단과 Cross Validation 결과를 결정론적으로 결합해 최종 Resolve 결정을 만든다. ticker lookup은 중간 `TickerResolvedEvent`만 만들며, Resolve node가 identity 검증 후 최종 `ResolvedNewsEvent`를 조립한다.

## 상태 전이

`REJECT`는 validation과 관계없이 REJECT다. 그 외 VERIFIED는 ACCEPT, PARTIALLY_VERIFIED는 REVIEW, CONFLICTED는 REJECT, INSUFFICIENT_EVIDENCE 또는 validation 없음은 기존 Screening decision을 유지한다.

## 범위

모든 final event는 downstream에 전달한다. LLM Resolve, 외부 검색, 추천·점수·분석 로직 변경은 포함하지 않는다.

## 구현 중 보완 기록

- Event identity index는 `HasNewsEvent` Protocol과 generic helper로 타입을 보존한다. Resolve 통계는 문자열이 아닌 `ResolvedDecisionType` Enum을 직접 비교한다.
- Resolve reason은 `strip()`으로 정규화한 뒤 최초 순서를 유지하며 중복·공백을 제거한다. identity 오류는 duplicate, unknown, missing, mismatch를 구분해 설명한다.
