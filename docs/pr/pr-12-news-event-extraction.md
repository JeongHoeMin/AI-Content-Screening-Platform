# PR #12 News Event Extraction 계약 및 Prompt 도입

## Summary

- 기존 `Post` 파이프라인을 유지하고 뉴스용 `Article` 도메인을 병렬로 추가한다.
- `ArticleEvaluationResult`는 기존 Post 평가 모델과 독립적으로 진화한다.
- `NewsEventExtractor`는 Protocol로 정의하며 실제 LLM 구현은 PR #13에서 추가한다.
- `NewsEventParser`는 JSON decode, LLM 응답 DTO 검증, Domain 변환만 담당한다.
- Prompt 입력, LLM 응답, Domain 모델을 각각 Internal, LLM, Domain 계약으로 분리한다.

## Domain Contracts

- `Article`은 기사 식별자, 본문, 출처, 발행 시각과 URL을 표현한다.
- `ArticleEvaluationResult`는 기사, 평가 점수, 관련성 여부와 평가 근거를 포함한다.
- `CompanyRelation`은 기사에서 확인되는 `DIRECT`, `INDIRECT` 관계만 허용한다.
- `ExtractedCompany`는 기업명과 관계만 포함하며 ticker를 포함하지 않는다.
- `NewsEvent`는 제목, 요약, 기업, 산업, 키워드와 추출 근거를 가진다.
- `NewsEvent`는 식별자가 없는 비영속 Value Object다.
- `NewsEventExtractor`는 평가 결과를 받아 이벤트 목록을 반환하는 비동기 Protocol이다.
- `NewsEventParser`는 LLM 응답과 원본 평가 결과를 받아 이벤트 목록으로 변환한다.

## LLM and Internal Contracts

- `ExtractedCompanyResponseItem`, `NewsEventResponseItem`,
  `NewsEventExtractionResponse`는 Domain과 분리된 엄격한 LLM 응답 DTO다.
- PromptTemplate과 Parser는 동일한 `NewsEventExtractionResponse` 계약을 공유한다.
- `NewsEventPromptInput`은 immutable 내부 DTO이며 PromptBuilder의 유일한 입력이다.
- PromptBuilder는 메시지만 조립하고 직렬화와 문자열 표현은 PromptTemplate에 위임한다.
- Prompt는 명시되거나 직접 연결되는 사실만 추출하며 ticker, 투자 판단, 감성,
  신뢰도, 영향도, 추천 및 수혜·피해·경쟁 관계 추론을 금지한다.

## Implementation Changes

- 뉴스 Domain 모델, LLM 응답 DTO, Extractor·Parser Protocol과 기본 Parser를 추가한다.
- Parser는 JSON decode, Pydantic 검증과 명시적인 DTO-to-Domain mapping만 수행한다.
- 잘못된 응답은 예외로 전파하며 부분 성공이나 자동 보정을 지원하지 않는다.
- 뉴스 이벤트 PromptTemplate과 PromptBuilder를 추가한다.
- 기존 Requester, Evaluator, Skill, Harness, Workflow는 변경하지 않는다.

## Test Plan

- 뉴스 Domain과 기존 Post 평가 Domain의 독립성을 검증한다.
- Extractor·Parser Protocol과 PromptInput 불변성을 검증한다.
- PromptBuilder 메시지 조립, Template 위임 및 응답 계약 표현을 검증한다.
- 빈 목록 및 단일·복수 이벤트의 DTO-to-Domain 변환과 순서 보존을 검증한다.
- 잘못된 JSON, 누락·추가 필드, 잘못된 enum과 분석 필드를 거부하는지 검증한다.
- 기존 테스트를 포함한 전체 `pytest`를 실행한다.

## Assumptions and Roadmap

- Parser는 현재 원본 `ArticleEvaluationResult`를 Domain 생성에 사용하지 않을 수 있다.
- 원본 입력은 향후 출처 추적, 중복 제거와 이벤트 병합을 위해 계약에 유지한다.
- 관련성이 없는 기사에서는 빈 이벤트 목록이 허용된다.
- PR #13은 LLM Requester와 `LLMNewsEventExtractor`, PR #14는
  `ArticleDeduplicator`, PR #15는 `TickerResolver`, PR #16은
  `ImpactAnalyzer`, PR #17은 `EvidenceAggregator`, PR #18은
  `RecommendationEngine`을 도입한다.
- `EvidenceAggregator`는 `List[CompanyImpact]`를 `InvestmentEvidence`로
  집계하며 최종 추천 판단은 수행하지 않는다.

## Commit Message

```text
feat: add news event extraction contracts
```

## Change Log

### 2026-07-29

- 미사용으로 오해되지 않도록 Parser가 `ArticleEvaluationResult`를 향후 출처
  추적, 중복 제거와 이벤트 집계를 위해 보존한다는 의도를 docstring에 기록했다.
- Domain 불변성을 강화하기 위해 industries, keywords, reasons 내부의 빈 문자열을
  거부하도록 변경했다. 컬렉션 자체의 최소 길이는 이번 PR 범위에 추가하지 않았다.
- Prompt에 포함된 JSON Schema와 `NewsEventExtractionResponse.model_json_schema()`가
  정확히 일치하는지 검증하는 계약 테스트를 추가했다.
- 기존 Evaluator Prompt와 News Event Prompt의 공개 export가 모두 유지되는지
  최종 패키지 구성을 확인했다.
