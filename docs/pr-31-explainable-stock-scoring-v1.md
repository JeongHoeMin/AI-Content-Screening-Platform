# PR31: Explainable Stock Scoring v1

## Summary

PR30은 `ImpactEvaluation`에서 observation과 Policy eligibility를 원자적으로 보존하고, eligible
observation 하나를 기존 `CompanyImpact` evidence 하나로 변환했다. 현재 scoring은 이 evidence의
`ImpactDirection`을 `+1.0`, `-1.0`, `0.0`으로 단순 합산하지만, 각 점수가 어떤 evidence에서
나왔는지 보여 주는 정형화된 breakdown과 교체 가능한 score policy 계약은 없다.

PR31은 기존 `EvidenceAggregation → ScoringResult → RecommendationResult` public 흐름을 유지하면서,
각 `CompanyImpact`가 정확히 하나의 immutable score contribution으로 변환되는 **설명 가능한
결정론적 Stock Scoring v1**을 정의한다. Scoring은 impact를 재판단하거나 recommendation을 만들지
않는다.

## Scope

- exhaustive `DirectionScoreCatalog`를 포함하는 immutable `ScoringPolicyConfig`를 scoring 정책의
  단일 진입점으로 정의한다.
- `CompanyImpact` 하나의 direction 해석을 보존하는 immutable `ScoreContribution` Domain을 추가한다.
- `CompanyScore`에는 contribution breakdown만 저장하고, 기존 `evidences`는 contribution에서 계산하는
  read-only property로 제공한다. score가 contribution 합과 일치하도록 validator로 고정한다.
- 새 deterministic `EvidenceAwareScoringStrategy`가 contribution을 만들고 합산하며,
  `DefaultScoringEngine`은 Strategy 결과를 조립만 하도록 유지한다.
- Bootstrap은 완성된 `ScoringPolicyConfig` 하나를 Strategy에 명시적으로 주입한다.
- PR31, Domain, Workflow, Architecture, ADR 및 scoring 테스트를 실제 계약에 맞춰 갱신한다.

## Non Goals

- 주가, 거래량, 재무제표, 시장 데이터, 외부 API 또는 실시간 최신성 조회
- LLM score, embedding score, 감성 분석, 자유 텍스트 재해석
- ranking, company 간 비교, score filtering, score cap/normalization, portfolio allocation
- recommendation threshold 또는 `RecommendationPolicy` 행동 규칙 변경
- PR30 `ImpactEvaluation`의 uncertainty·validation·reason code를 scoring weight로 사용하는 것
- Aggregation adapter가 보존하지 않는 event fact, uncertainty, validation provenance를 scoring에서
  복원하거나 추론하는 것

## Current State and Constraints

- Aggregation은 eligible `ImpactEvaluation`의 observation 하나를 legacy
  `CompanyImpact(company, direction)` 하나로 변환하고 company ID로 묶는다.
- 따라서 PR31의 Scoring 입력인 `CompanyEvidence.impacts`는 company와 direction만 보장한다.
  PR30 snapshot의 `event_fact`, `uncertainty`, `reason_code`, validation 상태는 현재 scoring 경계의
  입력이 아니다.
- 현재 `RuleScoringStrategy`는 direction별 숫자를 내부 mapping으로 관리하고, `CompanyScore`는
  float 합계와 원본 evidence tuple만 보관한다.
- Recommendation은 `CompanyScore.score`만 Policy 경계값으로 해석한다. PR31 default weight는 기존
  결과를 유지해야 하므로 positive `+1.0`, negative `-1.0`, neutral/unknown `0.0`이다.

## Approved Product Decisions

### 1. Scoring 입력과 책임

PR31 Scoring은 `EvidenceAggregation`만 입력으로 받는다.

```text
eligible ImpactEvaluation
    ↓ (PR30 aggregation adapter)
CompanyImpact
    ↓
CompanyEvidence
    ↓
EvidenceAwareScoringStrategy
    ↓
CompanyScore(score + contributions)
```

- `ImpactStrategy`는 direction observation만 만든다.
- `ImpactPolicy`는 eligibility evaluation만 만든다.
- Aggregation은 eligible observation을 evidence로 선택하고 company ID로 묶는다.
- Scoring은 전달받은 `CompanyImpact.direction`을 Score Catalog로 수치화할 뿐, observation을 수정하거나
  Policy exclusion을 재평가하지 않는다.
- Recommendation은 score를 행동으로 해석하며, Scoring은 buy/sell/hold를 만들지 않는다.

### 2. Direction Score Catalog 완전성

`DirectionScoreCatalog`는 immutable Pydantic registry이며 현재 `ImpactDirection`의 모든 값을
정확히 한 번씩 등록해야 한다.

각 `DirectionScoreEntry`는 다음을 가진다.

- `direction`
- `factor` (`POSITIVE_EVIDENCE`, `NEGATIVE_EVIDENCE`, `NON_DIRECTIONAL_EVIDENCE`)
- finite `weight`
- 안전한 `reason_code`

Entry는 finite float 여부를 검증한다. Catalog는 duplicate direction 또는 missing direction이 있으면
생성·bootstrap 시 fail-fast한다.
유효 direction이 런타임에 조용히 score 정책 없이 처리되는 것은 허용하지 않는다.

v1 default mapping은 다음과 같다.

| Direction | Factor | Weight | Reason Code |
| --- | --- | ---: | --- |
| `POSITIVE` | `POSITIVE_EVIDENCE` | `1.0` | `POSITIVE_DIRECTION_WEIGHT` |
| `NEGATIVE` | `NEGATIVE_EVIDENCE` | `-1.0` | `NEGATIVE_DIRECTION_WEIGHT` |
| `NEUTRAL` | `NON_DIRECTIONAL_EVIDENCE` | `0.0` | `NEUTRAL_DIRECTION_WEIGHT` |
| `UNKNOWN` | `NON_DIRECTIONAL_EVIDENCE` | `0.0` | `UNKNOWN_DIRECTION_WEIGHT` |

`UNKNOWN`은 PR30 Policy에서 normally eligible evidence가 아니지만, catalog 완전성과 defensive
consumer 계약을 위해 명시적으로 `0.0` entry를 가진다. 이 entry는 UNKNOWN을 eligible하게 만드는
정책이 아니다.

### 3. ScoreContribution 계약

`ScoreContribution`은 하나의 원본 `CompanyImpact`와 그 Catalog 해석을 원자적으로 보존하는 immutable
Pydantic 값이다.

```text
ScoreContribution
├── impact: CompanyImpact
├── factor: ScoreFactor
├── weight: float
├── value: float
└── reason_code: ScoreReasonCode
```

- `impact`는 Aggregation이 전달한 동일 `CompanyImpact` 객체를 참조한다.
- v1에서 `value`는 Catalog `weight`와 반드시 같으며 validator가 `value == weight`를 강제한다. count,
  recency, source, uncertainty multiplier를 추가하지 않는다.
- 모든 input evidence는 정확히 하나의 contribution을 만든다. Scoring은 dedup, merge, cancel,
  reorder, discard를 수행하지 않는다.
- positive와 negative evidence는 각각 보존하며, 합산 결과가 0이 되어도 contribution은 삭제하지 않는다.

### 4. CompanyScore breakdown 불변식

`CompanyScore`는 `company`, `score`, `contributions` tuple만 저장한다. 기존 `evidences` public contract는
`contributions`에서 계산하는 read-only property로 유지한다.

- `company`는 input `CompanyEvidence.company`와 동일 객체다.
- `evidences` property는 input `CompanyEvidence.impacts`와 같은 객체·순서로 contribution의 `impact`를
  반환한다.
- evidence와 contribution의 길이·순서·객체 identity는 두 tuple을 별도로 저장하지 않으므로 구조적으로
  보장된다.
- `score`는 contribution `value`의 정확한 합이다. float 계산은 `math.fsum`을 사용해 결정적인 합산
  기준을 하나로 고정한다.

score-sum 불변식은 `CompanyScore` Domain validator에서 fail-fast한다. 기존 consumer가 필요로 하는
`CompanyScore.score`와 `evidences` read-only contract는 유지한다.

### 5. Policy와 configuration 경계

- `ScoringPolicyConfig`는 `policy_version`, `min_weight`, `max_weight`, `catalog`를 Pydantic으로 검증하는
  immutable configuration 값이며 scoring 정책의 유일한 주입 경계다.
- `DirectionScoreEntry`는 direction, factor, reason code, finite weight를 소유한다.
  `DirectionScoreCatalog`는 `ImpactDirection` 전체의 중복·누락을 검증한다.
  `ScoringPolicyConfig`는 policy version과 허용 weight 범위를 소유하고, 모든 catalog entry weight가
  해당 범위 안에 있는지 검증한다.
- Strategy는 mapping이나 범위를 hard-code하지 않고 주입된 `config.catalog`를 조회한다.
- Catalog 교체는 product policy 변경이며 Domain enum이나 Aggregation을 변경하지 않는다.
- `policy_version`은 `ScoringResult`와 각 `CompanyScore`에 보존되어 score provenance를 제공한다.
  v1 config는 방향 weight의 부호를 강제하지 않는다. 정책적 positive/negative 의미는 Catalog entry와
  test로 명시한다.

## Proposed Interfaces

```text
EvidenceAggregation
    ↓
EvidenceAwareScoringStrategy(config)
    ├── ScoreContribution × input evidence
    └── CompanyScore
    ↓
ScoringResult
    ↓
existing RecommendationPolicy
```

- `ScoringStrategy.score()`는 모든 `CompanyEvidence`에 순서대로 정확히 하나의 `CompanyScore`를
  반환한다.
- `DefaultScoringEngine`은 injected strategy를 한 번 호출하고 그 tuple을 복사·정렬·filtering 없이
  `ScoringResult`에 보관한다.
- `EvidenceAwareScoringStrategy`는 `ScoringPolicyConfig` 하나만 주입받고 network, LLM, Prompt, Directory, database, cache를 호출하지
  않는다.
- malformed Catalog는 recoverable item error가 아니라 configuration error이므로 전파한다.

## Migration and Compatibility

- Default Catalog의 weight가 현재 rule policy와 같으므로 기존 score 값과 recommendation boundary
  결과는 변하지 않아야 한다.
- `CompanyScore`의 새 `contributions`와 `policy_version`은 score provenance를 보강하는 additive Domain 확장이다.
  CLI JSON schema는 이번 PR에서 변경하지 않는다. serialization 영향이 발견되면 versioned CLI schema
  결정은 별도 PR로 분리한다.
- PR31은 `CompanyImpact`를 확장하지 않는다. validation/uncertainty/event fact weight가 필요해지면
  Aggregation output contract의 provenance 확장을 먼저 별도 PR로 승인해야 한다.

## Test Plan

### Catalog and Domain

- default Catalog의 모든 direction/factor/weight/reason mapping을 검증한다.
- duplicate direction과 missing direction Catalog가 fail-fast하는지 검증한다.
- non-finite weight (`NaN`, positive/negative infinity), Catalog 범위 밖 weight, blank policy version을
  거부하는지 검증한다.
- `ScoreContribution`의 impact identity와 `value == weight` 불변식을 검증한다.
- `CompanyScore.evidences` property가 contribution의 impact를 같은 순서·객체 identity로 반환하는지,
  별도의 evidences 입력으로 contribution과 불일치하는 CompanyScore를 만들 수 없는지, score-sum
  불변식을 검증한다.

### Strategy and Engine

- positive, negative, neutral, unknown direction의 contribution과 score를 검증한다.
- 상충 evidence가 각각의 contribution으로 남고 0점으로 상쇄되어도 삭제되지 않는지 검증한다.
- 같은 company의 여러 evidence, 여러 company, 빈 aggregation의 order/cardinality/identity를 검증한다.
- Strategy와 Engine이 input을 수정하지 않고, strategy 예외와 invalid config를 감싸지 않고 전파하는지
  검증한다.

### Regression

- default Config에서 기존 `RuleScoringStrategy`의 score와 새 strategy의 score가 동일하고,
  `CompanyScore`와 `ScoringResult`가 configured policy version을 보존하는지 검증한다.
- existing `RecommendationPolicy`의 모든 threshold 경계 결과가 동일 score에서 바뀌지 않는지 검증한다.
- Resolve → Analyze → Aggregate → Score → Recommend workflow의 event/company ordering과 current public
  result contract를 회귀 검증한다.
- 전체 `uv run pytest`, `uv run python -m compileall app tests`, `git diff --check`를 실행한다.

## Documentation Updates

- `ROADMAP.md`: Phase 7을 PR31 implementation 완료 시 Completed로 갱신한다.
- `DOMAIN_MODEL.md`: ScoreContribution 원자화, DirectionScoreCatalog/ScoringPolicyConfig 소유 관계,
  CompanyScore evidence property와 policy version 계약을 추가한다.
- `WORKFLOW.md`: Score 단계의 input/output과 provenance 보존 책임을 갱신한다.
- `ARCHITECTURE.md`: scoring policy/catalog과 기존 recommendation 경계를 기록한다.
- `DECISION_LOG.md`: score direction mapping의 exhaustive registry와 breakdown 보존을 ADR로 기록한다.

## Proposed Commit Message

```text
feat: add explainable stock scoring
```

## Change Log

### 2026-07-30 — Initial approved implementation plan

- PR30 이후 Phase 7의 다음 구현 단위를 direction-based explainable Stock Scoring v1으로 정의했다.
- 현재 scoring 입력에 없는 EventFact, validation, uncertainty provenance를 임의로 복원하거나
  weight에 사용하지 않도록 범위를 제한했다.
- score contribution을 evidence와 1:1로 보존하고 default weight가 기존 score/recommendation 결과를
  바꾸지 않는 호환 계약을 확정했다.

### 2026-07-30 — Contribution and policy ownership hardening

- CompanyScore가 evidences와 contributions를 별도 tuple로 저장하지 않고 ScoreContribution만 저장하며,
  evidences는 read-only property로 계산하도록 계약을 변경했다.
- ScoringPolicyConfig를 policy version, weight range, Catalog를 포함하는 단일 주입 경계로 고정했고,
  Strategy는 config 하나만 받아 catalog를 조회하도록 통일했다.
- v1 `ScoreContribution.value == weight`와 score provenance를 위한 policy version 보존을 추가했다.
