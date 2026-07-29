# PR #18 Scoring Engine 구현

## Summary

- EvidenceAggregation을 회사별 정량 점수로 변환한 ScoringResult snapshot을
  생성한다.
- ScoringEngine은 결과 조립만, ScoringStrategy는 점수 계산만 담당한다.
- Value Object 도입과 Recommendation은 이번 범위에서 제외하며 RecommendationEngine은
  PR #19에서 ScoringResult를 입력으로 사용한다.

## Domain and Contracts

- CompanyScore는 CompanyEvidence.company와 동일 객체인 company, Strategy가 계산한
  float score, 그리고 CompanyEvidence.impacts와 동일 Tuple 객체인 evidences를
  보관한다.
- evidences는 점수의 설명 가능성을 위한 원본 근거다. Scoring은 근거를 요약,
  filtering, 재정렬, 대체하지 않는다.
- ScoringResult는 immutable scoring snapshot이며 Strategy가 반환한 companies Tuple을
  복사하지 않고 보관한다.
- ScoringStrategy는 모든 입력 CompanyEvidence에 대해 순서대로 정확히 하나의
  CompanyScore를 생성한다. 새 ResolvedCompany 또는 CompanyImpact를 만들거나 입력을
  수정하지 않는다.

## Current Default Rule Policy

- POSITIVE는 1.0, NEGATIVE는 -1.0, UNKNOWN과 NEUTRAL은 0.0으로 변환한다.
- RuleScoringStrategy는 읽기 전용 direction-score policy로만 direction을 점수로
  변환하고 각 회사 evidences의 점수를 단순 합산한다.
- ranking, filtering, recommendation, confidence, time weight, source reliability,
  market data, portfolio 관리와 LLM scoring은 수행하지 않는다.

## Responsibility Boundary

- Scoring은 qualitative evidence를 quantitative score로 변환한다.
- Scoring은 매수·보유·매도 판단, ranking, filtering, portfolio optimization, 시장
  분석, confidence 추정, explainability 생성을 수행하지 않는다.
- RecommendationEngine만 ScoringResult를 actionable recommendation으로 변환한다.

## Test Plan

- 방향별 점수, 혼합 근거 합산, Company·evidence Tuple identity, 순서, cardinality,
  빈 입력, 불변성과 결정론성을 검증한다.
- Engine의 Strategy Tuple 보존, DI, 빈 입력과 예외 전파를 검증한다.
- 전체 pytest, Python compile과 git diff 검사를 실행한다.

## Assumptions

- Direction-to-score 정책은 교체 가능한 현재 기본 Rule 정책이다.
- Scoring은 투자 추천이 아닌 수집 근거의 정량적 해석이다.
- ScoringResult는 PR #19 RecommendationEngine의 유일한 입력 Domain이다.

## Commit Message

feat: add scoring engine
