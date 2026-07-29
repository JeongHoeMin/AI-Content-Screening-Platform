# PR #14 Article Deduplicator 구현

## Summary

- 뉴스 이벤트 목록에서 동일 사건을 제거하는 첫 Deduplication 파이프라인을 추가한다.
- DuplicateStrategy는 사건 동일성을 판단하고, DefaultArticleDeduplicator는
  판단 결과로 최초 이벤트만 유지한다.
- Rule 구현 계약, 현재 기본 Rule 정책 및 현재 순차 구현 특성을 분리한다.

## Contracts

### DuplicateStrategy

- 구현 방식과 무관하게 두 NewsEvent가 동일 사건인지 판단하는 순수 계약이다.
- 결정론적이고 부수 효과가 없으며, 입력 Event를 수정하거나 Domain 객체를
  생성·병합하지 않는다.
- 판단은 대칭적이고 반사적이며 예외를 wrapping하지 않는다.

### RuleDuplicateStrategy

- Embedding, semantic search, LLM 또는 ML을 사용하지 않는 결정론적 Rule 기반
  전략이다.
- immutable frozen dataclass로 구현하고 생성 시
  keyword_similarity_threshold를 0.0..1.0 범위로 fail-fast 검증한다.
- 생성 이후 비교 정책은 변경할 수 없다.

### Current Default Rule Policy

- 기업명 집합과 industry 집합이 정확히 같아야 한다.
- 기업 비교는 ExtractedCompany.name만 사용하며 CompanyRelation은 동일 사건의
  역할 차이이므로 제외한다.
- keyword 집합 Jaccard 유사도는 현재 threshold 이상이어야 한다.
- title은 trim, lower, 연속 공백 축소 후 같아야 한다.
- 이 정책은 필요한 비교 조건만 정의하며 조건 평가 순서나 최적화 전략은 강제하지
  않는다.

### ArticleDeduplicator

- 입력 순서를 유지하고 첫 non-duplicate Event를 canonical Event로 유지한다.
- 후속 duplicate는 병합하지 않고 discard해 원본 정보와 입력 순서를 보존한다.
- Duplicate 판단을 전적으로 DuplicateStrategy에 위임하며 직접 비교 규칙을
  구현하지 않는다.
- 입력 List·Event를 수정하거나 새 NewsEvent를 생성하지 않는다.

## Implementation Changes

- app.deduplicators에 Strategy와 Deduplicator Protocol 및 기본 구현을
  추가하고 export한다.
- 현재 구현은 유지된 canonical Event와 순차 비교하고 첫 중복에서 즉시 skip한다.
- A, A, B, C, C에서는 현재 구현 특성상 Strategy가 7회 호출된다. 이는 공개
  계약이 아닌 테스트 대상이다.
- Event 병합·변환, Embedding/LLM 판단, cache, metrics, logging, retry, ticker
  resolution 및 투자 분석은 추가하지 않는다.

## Test Plan

- Rule 정책의 중복·비중복 판단, relation 제외, title 정규화, Jaccard와 빈
  keyword 규칙을 검증한다.
- Strategy의 결정론성, 대칭성, 반사성, 입력 불변성, threshold 불변성과 생성
  시점 범위 검증을 확인한다.
- Deduplicator의 최초 canonical 유지, 순서·identity 보존, 입력 불변성, 빈·단일
  입력, Strategy 호출 횟수와 예외 전파를 검증한다.
- 전체 pytest, compile 및 git diff 검사를 실행한다.

## Assumptions and Roadmap

- Default Rule Policy는 향후 Rule v2나 산업별 정책으로 대체·확장할 수 있다.
- DuplicateStrategy는 Embedding, Hybrid, LLM 전략으로 교체 가능한 순수 계약이다.
- PR #15부터 Deduplicator 출력이 TickerResolver의 입력으로 사용된다.

## Commit Message

feat: add article deduplicator
