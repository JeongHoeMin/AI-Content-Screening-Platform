# PR-47 투자 테마·뉴스 주제 수집 필터

## 목표

반도체·AI·대체에너지 같은 투자 테마와 실적·정책·공급망·기술 뉴스 주제를 대시보드에서 함께 선택하고,
조건을 만족하는 문서만 기존 분석 workflow에 전달한다.

## 구현 범위

- immutable `CollectionFilter`, versioned `ThemeCatalog`, `ArticleFilter`를 추가했다.
- 두 차원을 함께 선택하면 AND로 적용하고, 빈 선택은 기존 전체 수집을 유지한다.
- 대시보드는 다중 선택 UI, 실행 중 입력 잠금, 안전한 제외 건수 메시지를 제공한다.
- `collection_filter_snapshots`에 실행 ID, 선택값, catalog version, 수집/통과/제외 집계와 UTC 시각을 저장한다.
- 기사 원문·URL·prompt·provider raw response는 snapshot과 로그에 저장하지 않는다.

## 범위 제한

카탈로그는 보수적인 문자열 일치 v1이다. LLM 기반 의미 분류, 개별 기업명 조건, 임베딩 검색, 가격 성과와
자동 스케줄은 후속 PR로 분리한다.

## 리뷰 보완

- 영문 약어는 단어 경계로 일치시켜 일반 영단어 내부의 오탐을 막는다.
- 수집 건수는 provider Post 수가 아니라 실제 필터 입력으로 변환된 Article 수를 기준으로 저장한다.
