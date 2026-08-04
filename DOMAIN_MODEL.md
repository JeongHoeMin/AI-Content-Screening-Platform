# Domain 설계

## 기본 원칙

Domain 모델은 Pydantic 기반 immutable 값이며 외부 SDK와 실행 환경을 모른다. transport DTO는 외부 응답을 받아들이기 위한 최소 구조이고, Parser를 통과한 Domain 객체만 Policy와 Workflow의 입력이 된다. 문자열 JSON, boolean, 범위 밖 숫자처럼 LLM transport에서 흔한 오류를 Domain 계약으로 묵시 변환하지 않는다.

## 핵심 모델 흐름

```text
RawPost → Post / Article → NewsEvent
                         ↓
              ScreeningAssessment → ScreeningDecision
                         ↓
CrossValidationCandidate → CrossValidationAssessment → CrossValidationResult
                         ↓
                 ResolvedNewsEvent → ImpactAnalysis
                         ↓
          EvidenceAggregation → ScoringResult → RecommendationResult
```

## 기사와 이벤트

`Article`은 외부 기사 표준화 결과로서 id, 제목, 본문, source, 발행 시각, URL을 가진다. `NewsEvent`는 기사에서 추출한 투자 분석 대상 사실이며 제목, 요약, 기업·산업·키워드·근거를 보관한다. event는 기사 원문이나 provider 응답을 대체하지 않으며, 원본 article과의 연결은 workflow inference가 보존한다.

`NewsEvent.event_type`은 필수 상위 Domain Category이며 `CORPORATE_EVENT`, `LEGAL_EVENT`, `FINANCIAL_EVENT`, `PRODUCT_EVENT`, `MACRO_EVENT`만 허용한다. EventType은 Impact 전용 값이 아니며 새 EventFact가 기존 Category에 수용되면 추가하지 않는다. `event_facts`는 선택적 immutable tuple의 독립 Fact다. 순서는 extraction 관측 순서로 보존하고 동일 Fact는 첫 값만 남긴다. Fact와 Type의 관계는 EventFact Enum이 아니라 별도 immutable `EventTypeCompatibility` table이 소유하며, Parser가 주입된 table로 검증한다. table은 교체 가능하지만 하나의 table 안에서 EventFact Enum의 모든 값은 정확히 하나의 Type entry에만 귀속된다. Type을 결정하지 못한 event는 Parser가 recoverable event 오류로 제외한다.

EventFact가 없는 EventType-only event는 유효한 Domain Event다. 다만 Fact를 요구하는 후속 Rule Catalog의 입력은 아니다. Fact 오류는 유효 event와 sibling Fact를 버리지 않으며 Parser가 fact-local 오류로 기록한다. 여러 Fact를 복합 Fact로 합치거나 새로운 의미를 추론하지 않는다.

## 수집 필터 계약

`CollectionFilter`는 immutable 투자 테마 tuple과 뉴스 주제 tuple을 가진다. 초기 테마는 `SEMICONDUCTOR`,
`ARTIFICIAL_INTELLIGENCE`, `RENEWABLE_ENERGY`이고, 주제는 `EARNINGS`, `POLICY`, `SUPPLY_CHAIN`,
`TECHNOLOGY`다. 입력 중복은 최초 순서를 보존해 제거한다.

`ThemeCatalog`는 versioned 결정적 term mapping을 소유한다. 빈 filter는 항상 통과하고, 선택한 각 차원에서는
하나 이상이 일치해야 하며 두 차원이 모두 선택되면 AND로 동작한다. `CollectionFilterResult`는 원본 Article
identity를 유지한 통과 tuple과 제외 ID·이유·집계만 보관한다. `CollectionFilterSnapshot`은 실행 ID, 선택값,
catalog version, 수집/통과/제외 수, 이유 집계, UTC 시각만 보관하며 기사 원문·URL·prompt는 포함하지 않는다.

## Screening 계약

`ScreeningAssessment`는 `relevance`, `importance`, `credibility`의 0–100 실제 Python `int`, `requires_cross_validation`, 최대 3개의 정규화된 reasons로 구성된다. `ScreeningDecision`은 assessment와 원본 `NewsEvent`를 묶고 `ScreeningPolicy`가 낸 `ACCEPT`, `REVIEW`, `REJECT` 상태를 갖는다.

`ScreeningScorecard`는 LLM이 관측하는 9개 세부 점수와 영역별 근거를 보존한다. 관련성은 테마 직접성·주제 일치도·시장 전파 경로, 중요도는 영향 크기·범위/파급도·시간 민감도, 신뢰도는 출처 권위·근거 구체성·교차 확인/불확실성으로 구성한다. LLM은 총점을 반환하지 않으며 `ScreeningScorecardPolicy`가 versioned 가중 평균과 half-up 정수 반올림으로 세 총점을 계산한다. scorecard의 누락·범위 밖·비정수 값은 해당 event만 Parser가 제외하고 sibling을 보존한다.

LLM DTO에서 `50`과 `50.0`은 Domain int `50`으로 변환할 수 있다. `50.5`, 문자열 숫자, boolean, `NaN`, `Infinity`, 범위 밖 값은 event 오류이며 fallback score를 만들지 않는다.

## Cross validation 계약

`CrossValidationCandidate`는 내부 `candidate_id`, screening decision, 원본 기사, 비교 기사들을 갖는다. candidate ID는 correlation과 내부 검증용이며 prompt나 LLM response에 노출하지 않는다.

`CrossValidationAssessment`는 event별로 유효 evidence assessment를 보관한다. 각 evidence에는 비교 article identity, relation, matched/conflicting claim이 있다. OpenAI transport relation은 `supports`, `conflicts`, `unrelated`만 허용하고 Domain에서는 각각 `SUPPORTS`, `CONTRADICTS`, `UNRELATED`로 변환한다. `PARTIAL`은 기존 Mock/Domain 호환성을 위한 값으로 유지한다.

`CrossValidationResult`의 최종 상태(`VERIFIED`, `PARTIALLY_VERIFIED`, `CONFLICTED`, `INSUFFICIENT_EVIDENCE`)와 `ValidationEvidence`는 `CrossValidationPolicy`가 생성한다. LLM은 상태나 독립성 결정을 생성하지 않는다.

## Parser 결과와 오류 관측

LLM parser는 raw tuple 대신 immutable parse result를 반환한다. 결과에는 유효 assessment와 제한된 parse error가 분리되어 들어간다. 오류에는 제한 enum, batch-local event/evidence index, 내부 candidate ID만 포함하며 기사 본문, prompt, raw response, 예외 전문은 포함하지 않는다.

검증은 다음 순서를 따른다.

1. event/evidence index 타입, 범위, 중복, 누락을 확인한다.
2. relation, score, boolean, claim/reason의 타입과 형식을 확인한다.
3. 공백을 정규화하고 빈 문자열을 제거하며 순서를 보존해 중복을 제거한다.
4. Domain 최대 개수와 상호 형식 규칙을 적용한다.
5. 유효 sibling event/evidence만 입력 순서와 원본 object identity를 보존해 반환한다.

`supports`는 matched claim, `conflicts`는 conflicting claim, `unrelated`는 양쪽 claim이 비어 있어야 한다. 중복 index의 모든 응답은 무효다.

## 출처 독립성

독립 출처 수는 LLM이 아닌 `CrossValidationPolicy`가 계산한다. 비교 evidence 두 개는 정규화한 URL domain이 같거나 정규화한 `Article.source`가 같으면 같은 출처다. 이 관계의 연결 요소를 하나의 출처 그룹으로 취급한다. 따라서 A–B가 source로 같고 A–C가 domain으로 같다면 A·B·C는 하나의 그룹이다. 이는 독립성 과대평가를 막는 보수적 정책이다.

domain 정규화는 소문자화, port 제거, 선행 `www.` 제거만 수행한다. Public Suffix List 기반 등록 가능 도메인 추출이나 임의 subdomain 제거는 아직 하지 않는다. URL을 얻지 못하면 source로만 비교하며, domain과 source가 모두 없으면 독립 출처 수에 더하지 않는다.

`source`는 정확한 정규화 문자열 비교만 한다. 기본 비식별 목록은 `unknown`, `unknown source`, `n/a`, `na`, `none`, `null`, `news`, `newsroom`이다. `publisher`, `source`, `media`, `press`처럼 정상 명칭일 수도 있는 일반 단어는 목록에 넣지 않으며, 부분 문자열 비교도 금지한다.

## Company Resolution 계약

Company Resolution v1은 KRX 상장사만 다루며 versioned `CanonicalCompany` snapshot을 사용한다. snapshot은 local CSV 또는 KRX OpenAPI에서 만들 수 있다. `company_id`는 ticker·exchange·회사명과 독립적인 영구 identity이며 회사 동일성 비교의 기준이다. KRX ticker는 leading zero를 보존하는 6자리 문자열이고 exchange는 `KOSPI`, `KOSDAQ`, `KONEX` 중 하나다.

Directory는 normalized canonical name과 aliases의 name index에서 후보 사실만 반환한다. Policy는 distinct `company_id` 수가 1개면 `RESOLVED`, 2개 이상이면 `AMBIGUOUS`, 0개면 `UNRESOLVED`를 결정한다. alias collision은 다중 후보로 보존하며, 같은 company ID master row의 중복은 configuration error다.

모든 resolution observation과 `ResolvedCompany` snapshot은 directory version을 보관한다. local CSV와 KRX API snapshot version은 `YYYY-MM-DD`, empty directory version은 `empty`다. 모호·미해결 회사는 원본 name/relation/status를 보존하지만 canonical ID와 ticker는 갖지 않으며, 종목 evidence aggregation·score·recommendation에서는 제외한다.

## Impact Analysis 계약

`ImpactAnalysis`는 원본 `ResolvedNewsEvent` 동일 객체와 immutable `ImpactEvaluation` tuple을 보관하는 snapshot이다. `ImpactEvaluation`은 `ImpactPolicy`가 하나의 Strategy `ImpactObservation`에 대해 생성하는 결과이며, observation과 eligibility를 원자적으로 결합한다. `observations`는 evaluations에서 계산하는 read-only property이므로 별도 저장 tuple과 순서가 어긋날 수 없다. observation은 `scope`, `company`, `event_fact`, `direction`, `uncertainty`, Strategy 전용 `reason_code`를 가진다. `COMPANY` scope observation은 회사를 반드시 참조하고, `INDUSTRY`·`MARKET`·`MACRO` scope에는 회사를 넣지 않는다.

`ImpactDirection`의 `UNKNOWN`은 근거 부족을, `NEUTRAL`은 영향 없다는 적극적 판단을 뜻한다. 둘은 동일시하지 않는다. 모든 observation은 방향이나 resolution 상태와 무관하게 analysis snapshot에 보존한다.

v1 EventFact에는 명시된 `MAJOR_SUPPLY_CONTRACT`도 포함한다. 이는 공시나 기사에 계약 체결 사실이 직접 명시되고 계약 당사 기업이 DIRECT로 식별된 경우에만 사용한다. 계약 규모·이행 가능성·미래 실적은 추가로 추론하지 않는다. 기본 catalog는 이 계약 체결 사실을 positive observation으로 해석한다.

Direction은 versioned Impact Rule Catalog의 등록된 Fact, Direction, Reason Code 조합으로만 생성한다. Catalog는 모든 `EventFact`를 정확히 한 번씩 등록해야 하며 중복·누락은 fail-fast한다. v1에서 `CompanyRelation.DIRECT`만 direction 생성 대상이며 `INDIRECT`는 자동 전파 대상이 아니다. 각 Fact는 독립 observation을 만들고 상충 direction은 보존한다.

`ImpactPolicy`는 observation의 허용·제외와 downstream 전달 여부만 결정하는 filtering 계층이다. `ImpactEvaluation`은 observation과 eligibility를 함께 보관하며, eligible이면 reason이 null, ineligible이면 하나의 Policy 전용 `exclusion_reason`을 가진다. 우선순위는 `EVENT_REJECTED` → `EVENT_REVIEW_NOT_VERIFIED` → `COMPANY_NOT_RESOLVED` → `COMPANY_IDENTITY_MISSING` → `UNSUPPORTED_SCOPE` → `UNKNOWN_DIRECTION`이다. Policy는 Strategy observation의 identity와 순서를 유지하며 `direction`, `scope`, `reason_code`, `uncertainty`, company reference를 수정·교체·삭제하지 않는다. Aggregation adapter는 eligible evaluation의 observation 하나를 CompanyImpact 하나로 변환하며 병합·상쇄하지 않는다.

## Stock Scoring 계약

Scoring은 `EvidenceAggregation`의 `CompanyImpact(company, direction)`만 소비한다. immutable
`DirectionScoreCatalog`는 모든 `ImpactDirection`을 정확히 한 번 등록하고, `ScoringPolicyConfig`는
policy version, finite weight range, Catalog를 소유하는 유일한 정책 입력이다. Catalog 중복·누락,
non-finite 또는 범위 밖 weight는 fail-fast한다.

`ScoreContribution`은 원본 CompanyImpact와 factor, weight, value, reason code를 원자적으로 보존한다.
v1에서 value는 weight와 같으며 모든 evidence는 하나의 contribution으로 남는다. `CompanyScore`는
company, score, contributions만 저장하고, `evidences`는 contribution impact를 원래 순서·객체 identity로
노출하는 read-only property다. score는 contribution value의 `math.fsum`과 일치해야 한다.

`EvidenceAwareScoringStrategy`는 Config로부터 최종 immutable `ScoringResult`를 생성한다.
policy version은 회사별 값이 아니라 실행 단위 provenance이므로 ScoringResult만 보관한다.
`DefaultScoringEngine`은 Strategy 결과를 변경·복사·재조립하지 않고 동일 객체를 반환한다.

## Recommendation 계약

`RecommendationThresholdSnapshot`은 strong-buy, buy, sell, strong-sell 네 threshold를 가진 immutable
Domain Value다. 모든 값은 finite float이고 `strong_sell < sell < buy < strong_buy`를 Snapshot 단독 validator가
강제한다. `RecommendationPolicyConfig`는 nonblank policy version과 검증된 Snapshot만 소유하는 단일 정책
입력이다.

`RecommendationDecision`은 Policy가 하나의 `CompanyScore`에 대해 만든 immutable 결과이며,
`company_score`, action, action별 reason code, threshold snapshot을 원자적으로 보관한다. score는 중복 저장하지
않고 `company_score.score` property로 노출한다. validator는 score 구간, action, reason code, snapshot이 실제
ordered threshold 정책과 일치하는지 fail-fast한다. `RecommendationResult`는 실행 단위 policy version과
decision tuple만 저장한다. 기존 `companies` access는 별도 legacy view가 아니라 동일한
`RecommendationDecision` collection을 반환하는 read-only compatibility alias다.
CLI는 이 내부 Decision을 기존 `companies[].score`/`companies[].recommendation` schema로만 투영한다.

## Candidate Selection 계약

`RecommendationRankCatalog`은 모든 `RecommendationAction`을 정확히 한 번씩 등록하고, action 중복·누락,
negative/duplicate priority를 fail-fast한다. `eligible`은 교체 가능한 설정이 아니라 v1 제품 정책을 명시하는
Catalog 사실이다. STRONG_BUY/BUY만 eligible이고 나머지는 not eligible이며, 이 조합을 바꾸는 Catalog는
fail-fast한다. priority만 교체 가능한 ranking 요소이고 v1 ranking에는 eligible entry priority만 사용한다.
`RankingPolicyConfig`는 nonblank version, `max_candidates >= 1`, Catalog를 단일 immutable policy input으로
소유한다.

`CandidateEvaluation`은 원본 `RecommendationDecision`, status, reason code, input index, optional rank를
원자적으로 보존한다. SELECTED만 1 이상 rank를 가지고, NOT_ELIGIBLE과 OUTSIDE_LIMIT에는 rank가 없다.
`CandidateSelectionResult.evaluations`는 input index ascending의 canonical audit trail이며, candidates는 rank
ascending, excluded와 decisions는 input order로 계산한다. OUTSIDE_LIMIT reason은 action-independent하며 원래
action은 Decision에 보존된다.

action별 selected/not-eligible reason은 Candidate Domain helper가 유일하게 소유한다. helper는 해당 status를
가질 수 없는 action에 대해 명시적 ValueError를 내며, Policy와 Evaluation validator는 같은 helper를 사용한다.

## Policy 경계

Policy는 검증된 Domain 입력을 받아 결정만 반환한다. Policy는 Prompt·LLM·DB·네트워크를 호출하지 않는다. 점수 임계값, cross-validation 상태, resolve 결론, stock score, recommendation은 Policy/strategy가 소유하며 transport 오류나 model 편차에 의해 직접 바뀌지 않아야 한다.
