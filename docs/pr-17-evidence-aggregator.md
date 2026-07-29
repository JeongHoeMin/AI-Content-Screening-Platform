# PR #17 Evidence Aggregator 구현

## Summary

- ImpactAnalysis 목록을 회사별 CompanyEvidence로 그룹화한 EvidenceAggregation
  snapshot으로 집계한다.
- EvidenceAggregator는 결과 조립만, AggregationStrategy는 grouping만 담당한다.
- direction 수정, 점수, confidence, 시간 가중치와 recommendation을 추가하지 않는다.

## Domain and Contracts

- CompanyEvidence는 그룹에서 처음 만난 원본 ResolvedCompany를 canonical company로
  동일 객체 참조한다. canonical company는 그룹 identity의 대표일 뿐 원본
  CompanyImpact를 대체하거나 수정하지 않는다.
- CompanyEvidence는 동일 객체의 CompanyImpact Tuple을 입력 순서로 보관하며 모든
  CompanyImpact는 정확히 하나의 CompanyEvidence에만 속한다.
- EvidenceAggregation은 기존 ImpactAnalysis를 대체하지 않는 immutable
  aggregation snapshot이며 RecommendationEngine의 유일한 입력이다.
- AggregationStrategy는 모든 CompanyImpact를 정확히 한 CompanyEvidence에만
  포함하는 순수·결정론적 grouping 계약이다.
- EvidenceAggregator는 Strategy Tuple을 복사하지 않고 EvidenceAggregation에
  보관한다.

## Current Default Grouping Policy

- ticker가 있는 resolved CompanyImpact는 object identity가 아닌 ticker와 exchange
  값에 대한 ResolvedTicker equality로 그룹화한다.
- ticker가 None인 unresolved CompanyImpact는 각각 독립 CompanyEvidence로
  보존한다. 이름이나 다른 metadata가 같아도 병합하지 않는다.
- 이름, alias, relation, industry, direction과 다른 metadata로 회사 identity를
  추론하지 않는다.
- analyses 순서 후 각 analysis.impacts 순서로 flatten한다. 예를 들어 `A, B`와
  `A, C`는 `A, B, A, C`로 flatten한 뒤 `A, B, C` 그룹으로 집계한다.
- 그룹과 각 그룹 내부 impacts는 최초 등장 순서를 유지하며 정렬하지 않는다.

## Implementation Changes

- app.models에 CompanyEvidence와 EvidenceAggregation을 추가한다.
- app.aggregators에 Strategy·Aggregator Protocol과 Default 구현을 추가하고
  export한다.
- 현재 Strategy는 first-seen canonical company와 immutable Tuple만 생성한다.
- filtering, deduplication, direction 변경, score, confidence, weight, ranking,
  recommendation과 추가 ticker resolution은 수행하지 않는다.

## Test Plan

- 동일 ticker 집계, 다른 ticker 분리, unresolved 독립 보존, flatten 순서와
  모든 CompanyImpact의 정확히 한 번 포함을 검증한다.
- canonical company와 CompanyImpact identity, 원본 불변성, frozen Strategy를
  검증한다.
- Aggregator의 Tuple 보존, DI, 빈 입력과 Strategy 예외 전파를 검증한다.
- 전체 pytest, Python compile 및 git diff 검사를 실행한다.

## Assumptions

- grouping policy는 교체할 수 있지만 EvidenceAggregation Domain 계약은 바뀌지
  않는다.
- 시간 기반 weight, source 신뢰도, 시장 데이터, 뉴스 중요도, voting, ranking,
  priority, recommendation과 추가 direction 판단은 후속 범위다.

## Commit Message

feat: add evidence aggregator
