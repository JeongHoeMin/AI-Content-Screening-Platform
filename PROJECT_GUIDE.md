# AI Content Screening Platform

> AI 기반 뉴스 스크리닝 및 투자 추천 플랫폼

---

# 1. 프로젝트 목표

본 프로젝트의 최종 목표는 단순한 뉴스 요약 시스템이 아니다.

매일 수집되는 뉴스, 경제 기사, 정치 기사, 기업 공시 등의 정보를 분석하여 **투자 가치가 있는 이벤트를 식별하고, 최종적으로 매수·관망·주의 종목을 추천하는 AI 시스템**을 구축하는 것이 목적이다.

최종 Workflow는 다음과 같다.

```text
News Collection → Normalization → Event Extraction → AI Screening
→ Cross Validation → Resolve → Event Analysis → Company Mapping
→ Impact Analysis → Stock Scoring → Portfolio Recommendation
```

---

# 2. 핵심 원칙

## 2.1 LLM은 판단을 보조한다

LLM은 기사 요약, 이벤트 추출, 기사 관계 분석, 이벤트 중요도 평가, 영향 분석만 수행한다. LLM은 시스템의 최종 의사결정을 내려서는 안 된다.

## 2.2 최종 결정은 Policy가 수행한다

다음은 반드시 Policy에서 수행한다.

- Accept / Review / Reject
- Verified 여부
- Independent Source 계산
- Stock Score 계산
- Recommendation 생성

LLM은 Decision을 생성하지 않는다.

## 2.3 Prompt와 Business Logic은 분리한다

Prompt는 자연어이고 Business Logic은 코드다. Prompt 안에 비즈니스 규칙을 넣지 않는다.

```text
LLM은 supports/conflicts만 반환
↓
Policy가 Verified를 결정
```

예를 들어 `Independent source가 2개 이상이면 Verified` 같은 규칙을 Prompt에 넣지 않는다.

## 2.4 Parser는 모든 입력을 검증한다

Transport DTO는 최소한의 구조만 보장하고 실제 검증은 Parser에서 수행한다.

- 타입
- 범위
- 중복
- 누락
- Index
- Enum

## 2.5 부분 성공을 우선한다

Event 하나의 실패가 Batch 전체 실패가 되어서는 안 된다. 가능한 한 성공한 sibling 결과를 유지한다.

```text
Success
Success
Failure
Success
```

## 2.6 Non Goals

현재 프로젝트는 다음을 목표로 하지 않는다.

- 실시간 초단위 자동매매
- 가격 예측 모델
- 기술적 분석 기반 투자 전략
- GPT가 직접 투자 결정을 수행하는 시스템
- 하나의 기사만으로 종목을 추천하는 시스템

본 프로젝트는 뉴스 이벤트를 구조화하고 검증하여 투자 판단에 필요한 근거를 생성하는 것에 집중한다.

---

# 3. 프로젝트 아키텍처

```text
Provider → Normalizer → Article → Extractor → NewsEvent → Screening
→ Cross Validation → Resolve → Analysis → Recommendation
```

---

# 4. Layer 규칙

## Provider

RSS, Reddit, SEC, DART, News API 등 외부 데이터를 수집한다. Provider는 데이터를 가공하지 않는다.

## Normalizer

Provider별 데이터를 공통 `Article`로 변환하고 Provider 종속 데이터를 제거한다.

## Extractor

`Article`을 `NewsEvent`로 변환한다.

## Screener

Event의 Relevance, Importance, Credibility를 평가한다.

## Cross Validator

다른 기사와 비교해 Supports, Conflicts, Unrelated 관계를 생성한다.

## Resolver

Screening과 Cross Validation 결과를 바탕으로 Accept, Review, Reject를 결정한다.

## Analyzer

Event가 기업, 산업, 시장, 거시경제에 미치는 영향을 분석한다.

## Recommendation

최종 투자 추천을 생성한다.

---

# 5. Domain 설계 원칙

- Domain 객체는 Immutable을 기본으로 한다.
- Domain은 외부 API를 몰라야 한다.
- Transport DTO는 Domain으로 변환되어야 한다.
- Business Logic은 Domain 객체끼리만 수행한다.

# 6. Parser 설계 원칙

Parser는 `DTO → Validation → Domain`으로만 동작한다. Policy, Database, LLM을 호출하지 않는다.

# 7. Policy 설계 원칙

Policy는 `입력 → 결정 → 출력`만 수행한다. Prompt 생성이나 OpenAI 호출을 수행하지 않는다.

# 8. Logging 규칙

로그에 다음을 절대로 출력하지 않는다.

- 기사 원문
- Prompt
- API Key
- 개인정보

로그에는 Event 개수, 처리 시간, 실패 이유처럼 안전한 관측 정보만 기록한다.

# 9. 테스트 원칙

Mock Mode와 OpenAI Mode는 동일한 Workflow를 사용한다. Mock은 Prompt를 우회하지만 Business Logic은 동일해야 한다.

# 10. AI 사용 원칙

AI는 코드·테스트·문서 생성에 사용할 수 있다. 다만 AI가 작성한 코드는 반드시 Policy, Parser, 테스트를 통과해야 한다.

# 11. 현재 구현 범위

완료:

- Provider
- Normalizer
- Event Extraction
- AI Screening
- Cross Validation
- Resolve

예정:

- Company Resolver
- Impact Analyzer
- Stock Scoring
- Recommendation
- Portfolio Optimization

# 12. 장기 목표

최종적으로 시스템은 매일 오전 뉴스 수집, 이벤트 추출, 교차 검증, 기업 영향 분석, 종목 점수 계산, 추천 종목 생성을 수행한다.

최종 출력 예시는 다음과 같다.

```text
★★★★★ 삼성전자

이유

- Reuters
- Bloomberg
- 연합뉴스

3개 독립 출처 검증

HBM 생산 확대
AI 서버 투자 증가
긍정 영향 91점
```

사용자는 단순히 뉴스를 읽는 것이 아니라 **"오늘 어떤 종목을 왜 봐야 하는지"**를 이해할 수 있어야 한다.
