# PR #19 Recommendation Engine 구현 및 Refinement

## Summary

- ScoringResult를 회사별 투자 행동이 담긴 RecommendationResult로 변환한다.
- Recommendation은 점수를 계산하거나 evidence를 재분석하지 않는 Decision Layer다.
- RecommendationEngine은 결과 조립만 담당하고 RecommendationPolicy가 행동 결정
  정책을 담당한다.

## Domain and Contracts

- Recommendation은 현재 Policy가 선택한 행동만 표현하며 threshold를 포함하지 않는다.
- CompanyRecommendation.score는 ScoringEngine이 생성한 동일한 CompanyScore 객체를
  참조한다. Company, score, evidences를 복사하거나 새 CompanyScore를 만들지 않는다.
- RecommendationResult는 immutable decision snapshot이다. companies의 순서는 입력
  ScoringResult.companies의 순서와 동일하다.
- RecommendationPolicy는 모든 입력 CompanyScore에 대해 순서대로 정확히 하나의
  CompanyRecommendation을 만들고, CompanyScore를 생성하거나 교체하지 않는다.
- DefaultRecommendationEngine은 Policy 반환 Tuple을 복사, 수정, filtering, sorting,
  ranking 없이 RecommendationResult에 그대로 보관한다.

## Current Rule Policy

- RuleRecommendationPolicy의 각 immutable RecommendationRule은 자신의 score predicate와
  결과 Recommendation을 보관한다.
- Rules are evaluated from top to bottom. The first matching rule wins. Rule order is
  therefore part of the current policy.
- 현재 순서와 결과는 `>= 2.0` strong buy, `>= 1.0` buy, `> -1.0` hold, `> -2.0` sell,
  그리고 일치 Rule이 없을 때 strong sell이다. 따라서 `-1.0`은 sell이고 `-2.0`은
  strong sell이다.
- predicate가 경계와 구간의 의미를 소유하므로 Policy 알고리즘은 이를 해석하지 않는다.

## Responsibility Boundary

- Recommendation은 score를 정책 기반 투자 행동으로 해석하고 CompanyRecommendation을
  생성한다.
- Recommendation은 score 계산, evidence 재분석, direction 수정, ranking, filtering,
  portfolio, risk, market data, time weight, source reliability, LLM 판단, explanation
  생성을 수행하지 않는다.
- Recommendation은 회사 간 비교나 우선순위를 계산하지 않는다. RecommendationResult는
  향후 RankingEngine의 입력 Domain이다.

## Test Plan

- 모든 Rule 경계, 순서, cardinality, CompanyScore 및 Policy Tuple identity, 빈 입력,
  불변성, 결정론성과 입력 비변경을 검증한다.
- Engine의 DI, Policy 단일 호출, 예외 무가공 전파를 검증한다.

## Assumptions

- Recommendation은 회사 하나에 대한 정책 기반 의사결정이다.
- 향후 Aggressive, Conservative, ETF, Long-term Policy는 Rule predicate를 교체하거나
  추가하여 확장한다. Ranking, Explanation, Portfolio, Risk는 별도 계층으로 추가한다.

## Internal Rule Representation

- `_RecommendationRule`과 `_RULES`는 RecommendationPolicy의 internal implementation
  detail이며 public API의 일부가 아니다.
- `_RecommendationRule.predicate`는 score가 Rule에 속하는지를 판정하고 threshold,
  inclusive, exclusive, interval 같은 boundary semantics를 모두 캡슐화한다.
- Recommendation 알고리즘은 Rule을 위에서 아래로 실행해 첫 일치 결과를 선택할 뿐,
  predicate의 threshold 의미를 직접 해석하지 않는다.
- `_RULES`는 `Final` Tuple로 선언된 현재 정책이다. `Final`은 정적 타입 계약이고,
  runtime 불변성 검증 대상은 아니다.

## Engine Responsibility

- RecommendationPolicy owns every decision. RecommendationEngine owns only
  orchestration.
- Engine은 configured Policy를 한 번 호출하고 Policy가 반환한 동일 Tuple을 복사,
  수정, 재정렬 없이 RecommendationResult에 보관한다. Recommendation Rule을 직접
  평가하지 않는다.

## Refinement #2 Record (2026-07-29)

- 변경 이유: Rule 표현이 Policy 내부 구현임을 명확히 하고 공개 계약 중심의 테스트
  전략을 유지한다.
- 결정: Rule을 `_RecommendationRule`로 은닉하고 `_RULES`를 `Final`로 선언한다.
  CompanyRecommendation, RecommendationResult, Policy, Engine의 identity와 책임
  경계를 docstring으로 보강한다.
- 범위 제한: Recommendation 결과, score 경계값, workflow/harness 연결, 새 Policy 추가는
  변경하지 않는다. private symbol, `Final`, frozen 구현 세부사항을 테스트하지 않는다.
