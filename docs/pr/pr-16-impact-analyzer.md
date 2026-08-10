# PR #16 Impact Analyzer 구현

## Summary

- ResolvedNewsEvent 목록에서 회사별 영향 방향을 담은 ImpactAnalysis 목록을
  생성한다.
- ImpactAnalyzer는 결과 조립만, ImpactStrategy는 영향 방향 판단만 담당한다.
- Rule 기반 Strategy만 추가하며 추천, 점수, confidence와 추가 ticker resolution은
  구현하지 않는다.

## Domain and Contracts

- CompanyImpact는 입력 ResolvedCompany의 동일 객체와 방향을 보관한다.
- ImpactAnalysis는 입력 ResolvedNewsEvent의 동일 객체와 immutable impacts Tuple을
  보관하는 analysis snapshot이다.
- UNKNOWN은 판단 근거 부족, NEUTRAL은 영향 없음의 적극적 판단을 뜻한다. 기본
  Rule은 둘을 구분할 수 없어 UNKNOWN만 반환한다.
- ImpactStrategy는 각 입력 회사에 대해 순서와 identity를 보존한 CompanyImpact
  하나를 반환하는 순수·결정론적 계약이다.
- ImpactAnalyzer는 Strategy가 만든 immutable Tuple을 복사하지 않고 새
  ImpactAnalysis에 보관한다.

## Implementation Changes

- app.models에 ImpactDirection, CompanyImpact, ImpactAnalysis을 추가한다.
- app.analyzers에 Strategy·Analyzer Protocol과 Rule·Default 구현을 추가하고
  export한다.
- Rule Strategy는 title과 summary를 줄바꿈으로 연결한 텍스트만 사용한다.
- 현재 Rule은 공장 증설·설비 투자·투자 확대를 POSITIVE, 소송·리콜·계약 종료를
  NEGATIVE로 판단한다. 상충 또는 기타는 UNKNOWN이다.
- 현재 구현은 하나의 Event-level direction을 모든 회사에 동일하게 적용한다.
  향후 Strategy는 회사별 direction을 다르게 만들 수 있다.

## Test Plan

- 기본 Rule의 positive, negative, unknown, 상충 및 계약 체결 제외를 검증한다.
- title과 summary 결합, 세 Company의 순서·identity·동일 direction, 불변성과
  결정론성을 검증한다.
- Analyzer의 순서·identity·Tuple 보존, 빈 입력, DI, 예외 전파를 검증한다.
- 전체 pytest, Python compile 및 git diff 검사를 실행한다.

## Assumptions

- ImpactStrategy는 Rule, LLM, Hybrid 구현으로 교체 가능한 순수 계약이다.
- ImpactAnalysis는 PR #17 EvidenceAggregator의 유일한 입력 Domain이다.
- confidence, score, evidence, recommendation, 시장 데이터와 주가 분석은 이번
  범위가 아니다.

## Commit Message

feat: add impact analyzer
