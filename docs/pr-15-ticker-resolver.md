# PR #15 Ticker Resolver 구현

## Summary

- NewsEvent의 기업명을 ticker와 exchange로 해석해 ResolvedNewsEvent snapshot을
  생성한다.
- TickerLookup은 이름 조회만, DefaultTickerResolver는 조회 결과 조립만 담당한다.
- StaticTickerLookup만 구현하며 외부 API, DB, cache와 투자 분석은 추가하지 않는다.

## Domain and Contracts

- ResolvedTicker는 시장 식별 정보만 표현하며 거래 가능성·시장 데이터·투자 의미를
  담지 않는다.
- ResolvedCompany는 원본 회사명과 relation을 보존하고 조회 실패를 ticker=None인
  정상 Domain 상태로 표현한다.
- ResolvedNewsEvent는 resolution 완료 시점의 immutable snapshot이다. 원본
  NewsEvent는 모든 Event metadata의 source of truth로 동일 객체를 참조한다.
- TickerLookup은 부수 효과 없이 회사명을 ResolvedTicker 또는 None으로 조회하는
  순수 계약이다. 입력 문자열을 변경하지 않으며 정규화는 구현체 내부 정책이다.
- TickerResolver는 Lookup에 모든 resolution을 위임하고 새로운 Resolved Domain만
  만든다.

## Implementation Changes

- app.models에 ResolvedTicker, ResolvedCompany, ResolvedNewsEvent frozen
  dataclass를 추가한다. resolved companies는 Tuple로 보관한다.
- app.resolvers에 Lookup과 Resolver Protocol, StaticTickerLookup,
  DefaultTickerResolver를 추가하고 export한다.
- StaticTickerLookup은 Mapping key를 정규화하고 중복 key를 검증한 뒤 방어 복사한
  read-only lookup table을 만든다.
- 현재 정규화 정책은 trim, lower, 연속 공백 축소다. Unicode, NFKC, locale 정책은
  포함하지 않는다.
- Resolver는 회사 순서대로 cache 없이 lookup하고 원본 이름을 그대로 담은
  ResolvedCompany를 생성한다.
- ticker resolution은 이 단계에서 완료되며 이후 단계는 ResolvedNewsEvent를
  소비하고 추가 resolution을 수행하지 않는다.

## Test Plan

- Static lookup의 등록·미등록·정규화 조회, immutable table, 외부 Mapping 격리,
  정규화 key 충돌과 반복 resolve 이후 상태 보존을 검증한다.
- Resolver의 순서·identity·원본 보존, 성공·실패 resolution, 모든 company lookup,
  예외 전파, DI와 빈 입력을 검증한다.
- 전체 pytest, Python compile 및 git diff 검사를 실행한다.

## Assumptions

- Static mapping은 이름당 하나의 ResolvedTicker만 표현한다.
- ticker 다중 후보 선택, retry, logging, metrics, Event 수정·병합, 영향 분석과
  추천은 이번 범위가 아니다.
- PR #16 ImpactAnalyzer는 ResolvedNewsEvent를 유일한 입력 Domain으로 사용한다.

## Commit Message

feat: add ticker resolver
