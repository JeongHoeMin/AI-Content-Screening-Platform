# PR32: Explainable Recommendation v1

## Summary

PR31은 `CompanyImpact`를 `ScoreContribution`으로 해석하고 immutable `CompanyScore` 및
`ScoringResult`에 score provenance를 보존했다. 현재 Recommendation은 score를 ordered threshold와
비교해 action만 반환하므로, 왜 해당 action이 선택됐는지와 적용된 threshold 정책을 정형화해
보존하지 않는다.

PR32는 기존 5개 recommendation action과 모든 score boundary 결과를 변경하지 않으면서,
`CompanyScore` 하나와 Recommendation Policy의 판단을 원자적으로 보존하는 **Explainable
Recommendation v1**을 정의한다. Recommendation은 scoring을 재수행하거나 evidence/contribution을
재해석하지 않는다.

## Scope

- 기존 action을 `STRONG_BUY`, `BUY`, `HOLD`, `SELL`, `STRONG_SELL` 그대로 유지한다.
- immutable Pydantic `RecommendationThresholdSnapshot`, `RecommendationPolicyConfig`,
  `RecommendationDecision`, `RecommendationResult`를 추가한다.
- action별 `RecommendationReasonCode`와 decision validator로 score/action/reason/threshold 일치를
  fail-fast 검증한다.
- `RecommendationPolicy`가 최종 `RecommendationResult`를 생성하도록 바꾸고,
  `DefaultRecommendationEngine`은 동일 객체를 그대로 반환하도록 전환한다.
- Bootstrap, Recommendation/Workflow Domain, ADR, Roadmap, PR32 문서와 regression test를 갱신한다.

## Non Goals

- score 계산, `ScoreContribution` 재해석, direction 변경 또는 `ScoringResult` 교체
- company ranking, top-N candidate 선택, tie-break, filtering
- portfolio 구성, position sizing, 투자 금액 배분, 자동 주문
- market data, risk/uncertainty/confidence weighting, profile별 policy, score normalization
- LLM 설명문, 자연어 투자 조언 또는 새로운 외부 데이터 조회
- CLI JSON schema 변경

## Current State and Compatibility

현재 `RuleRecommendationPolicy`는 아래 순서로 threshold를 평가한다.

```text
score >= 2.0  → STRONG_BUY
score >= 1.0  → BUY
score > -1.0  → HOLD
score > -2.0  → SELL
otherwise     → STRONG_SELL
```

따라서 실제 구간은 다음과 같다.

| Action | v1 score interval |
| --- | --- |
| `STRONG_BUY` | `score >= strong_buy_threshold` |
| `BUY` | `buy_threshold <= score < strong_buy_threshold` |
| `HOLD` | `sell_threshold < score < buy_threshold` |
| `SELL` | `strong_sell_threshold < score <= sell_threshold` |
| `STRONG_SELL` | `score <= strong_sell_threshold` |

Default threshold는 `strong_buy=2.0`, `buy=1.0`, `sell=-1.0`, `strong_sell=-2.0`이며,
PR32 default policy는 이 action 및 boundary 결과를 정확히 유지한다.

## Approved Product Decisions

### 1. Threshold policy의 단일 진입점

`RecommendationPolicyConfig`는 immutable Pydantic 값이며 다음만 소유한다.

```text
RecommendationPolicyConfig
├── policy_version
└── threshold_snapshot: RecommendationThresholdSnapshot
```

`RecommendationThresholdSnapshot`은 threshold 값 자체를 소유하는 immutable Pydantic Domain Value이며,
다음 finite float을 보관한다.

```text
strong_buy_threshold
buy_threshold
sell_threshold
strong_sell_threshold
```

Snapshot은 단독 생성 시 finite float 여부와 다음 순서를 validator로 fail-fast 검증한다.

```text
strong_sell_threshold < sell_threshold < buy_threshold < strong_buy_threshold
```

`RecommendationPolicyConfig`는 `policy_version`과 검증된 `threshold_snapshot`만 소유하는 immutable
정책의 단일 진입점이다. Config는 blank policy version만 직접 검증하며 threshold의 finite/order 규칙을
중복 검증하지 않는다. NaN/positive infinity/negative infinity threshold는 Snapshot이 거부한다.
Bootstrap은 완성된 default config 하나를 생성해 Policy에 주입한다. Mock/OpenAI workflow는 같은 default
config instance를 사용한다.

### 2. Decision 원자화

`RecommendationDecision`은 하나의 `CompanyScore`와 그 Policy 결과를 함께 보관하는 immutable
Pydantic 값이다.

```text
RecommendationDecision
├── company_score: CompanyScore
├── action: RecommendationAction
├── reason_code: RecommendationReasonCode
└── threshold_snapshot: RecommendationThresholdSnapshot
```

- `score`는 저장하지 않고 `company_score.score`를 반환하는 read-only property다.
- `company_score`는 input `ScoringResult.companies`의 동일 객체를 참조한다.
- threshold snapshot은 decision 시점의 Policy threshold를 보존하며, decision마다 독립 숫자 필드를
  중복 저장하지 않는다.
- action, reason code, score interval, threshold snapshot이 일치하지 않는 Decision은 validator가
  fail-fast한다.

Reason code는 action별로 유일하다.

| Action | Reason code |
| --- | --- |
| `STRONG_BUY` | `SCORE_AT_OR_ABOVE_STRONG_BUY_THRESHOLD` |
| `BUY` | `SCORE_AT_OR_ABOVE_BUY_THRESHOLD` |
| `HOLD` | `SCORE_WITHIN_HOLD_RANGE` |
| `SELL` | `SCORE_AT_OR_BELOW_SELL_THRESHOLD` |
| `STRONG_SELL` | `SCORE_AT_OR_BELOW_STRONG_SELL_THRESHOLD` |

`SELL`과 `STRONG_SELL` reason code는 threshold 방향을 설명하지만, validator는 위의 전체 구간을
동시에 적용해 stronger action과의 경계를 보장한다.

### 3. 결과와 하위 호환 property

`RecommendationResult`는 recommendation 실행 단위의 immutable 결과다.

```text
RecommendationResult
├── policy_version
└── decisions: tuple[RecommendationDecision, ...]
```

policy version은 회사별 속성이 아니라 Recommendation Policy 실행의 provenance이므로 Result만
보관한다. `ScoringResult.policy_version`과 `RecommendationResult.policy_version`은 서로 다른
policy layer의 version이며 같을 필요가 없다.

기존 `companies` public access는 `decisions`에서 계산하는 read-only property로 유지한다. 별도
companies tuple을 저장하지 않으므로 decision/company score 대응의 길이·순서·identity는 구조적으로
보장된다.

기존 `Recommendation` enum은 `RecommendationAction`의 backwards-compatible alias로 유지한다.
`RecommendationDecision`은 기존 `CompanyRecommendation`의 canonical replacement이며, 기존
`recommendation` access는 `action`을 반환하는 read-only property로 제공한다. 기존 `score` field가
참조하던 CompanyScore는 명확한 `company_score` field로 이전하고, 새 `score` property는 float score를
반환한다. 이 Domain field migration은 CLI schema를 변경하지 않으며 모든 internal consumer/test를
같은 PR에서 갱신한다.

### 4. Policy와 Engine 책임

```text
ScoringResult
    ↓
RecommendationPolicy(config)
    ↓
RecommendationResult(decisions + policy_version)
    ↓
DefaultRecommendationEngine
    ↓
same RecommendationResult identity
```

- `RecommendationPolicy.recommend()`는 input score마다 순서대로 정확히 하나의 Decision을 담은 최종
  immutable `RecommendationResult`를 생성한다.
- Policy는 score를 다시 계산하거나 contribution/evidence를 읽어 action을 바꾸지 않는다.
- `DefaultRecommendationEngine`은 configured Policy를 정확히 한 번 호출하고, 반환된 Result 객체를
  수정·복사·재조립·정렬·filtering 없이 동일 identity로 반환한다.
- configuration error와 programming error는 숨기거나 recoverable item error로 변환하지 않고 전파한다.

## Test Plan

### Domain and config

- default snapshot의 네 threshold와 strict ordering을 검증한다.
- Snapshot 단독 생성에서 non-finite threshold와 invalid threshold ordering을 reject하는지 검증한다.
- Config가 blank policy version을 reject하고 이미 유효한 Snapshot을 단일 정책 입력으로 보관하는지
  검증한다.
- 각 action에 대해 reason code와 score interval이 일치하는지 검증한다.
- action/reason mismatch, score/action mismatch, snapshot/action mismatch Decision이 fail-fast하는지 검증한다.
- `decision.score == decision.company_score.score`, CompanyScore identity, decision 순서 및
  `RecommendationResult.companies` read-only property의 대응을 검증한다.

### Policy, engine, regression

- strong buy/buy/hold/sell/strong sell의 바로 위·동일·바로 아래 모든 threshold boundary를 검증한다.
- 각 input CompanyScore가 정확히 하나의 Decision이 되고, 빈 ScoringResult가 빈 Result를 만드는지 검증한다.
- Policy가 configured recommendation policy version을 보존하는지 검증한다.
- Engine이 Policy가 반환한 동일 RecommendationResult 객체를 반환하고 Policy를 한 번만 호출하는지 검증한다.
- 기존 ordered rule policy와 default Config의 action 결과가 모든 boundary에서 동일한지 검증한다.
- Score → Recommend → Workflow의 ordering, CompanyScore identity, current public CLI result contract를 회귀 검증한다.
- 전체 `uv run pytest`, `uv run python -m compileall app tests`, `git diff --check`를 실행한다.

## Documentation Updates

- `ROADMAP.md`: PR32 구현 완료 시 Phase 8 상태와 산출물을 Explainable Recommendation v1 범위에 맞춘다.
- `DOMAIN_MODEL.md`: Decision 원자화, Result-level policy version, compatibility property를 기록한다.
- `WORKFLOW.md`: Recommend 단계의 final Result 생성과 Engine identity 계약을 기록한다.
- `ARCHITECTURE.md`: Recommendation Config/Policy와 Scoring Policy 분리를 추가한다.
- `DECISION_LOG.md`: ordered threshold snapshot과 decision provenance를 ADR로 기록한다.

## Proposed Commit Message

```text
feat: add explainable recommendation decisions
```

## Change Log

### 2026-07-30 — Initial approved implementation plan

- PR31 score provenance를 소비하는 다음 단위를 Explainable Recommendation v1으로 정의했다.
- 기존 5개 action과 실제 comparison order/boundary를 제품 계약으로 고정하고, action별 reason code와
  threshold snapshot을 decision에 보존하도록 했다.
- ranking, candidate selection, portfolio allocation, risk/profile은 PR33 이후 범위로 분리했다.

### 2026-07-30 — Threshold value ownership hardening

- threshold finite/order validator를 `RecommendationThresholdSnapshot`에 귀속하고, Config는 policy
  version과 검증된 Snapshot을 조립하는 단일 진입점으로만 제한했다.
- Snapshot 단독 fail-fast와 Config의 blank version 검증을 별도 테스트 계약으로 분리했다.

### 2026-07-30 — Implementation completed

- immutable Pydantic Recommendation Domain, ordered threshold validator, action별 reason code와 decision
  consistency validator를 구현했다.
- Policy가 final `RecommendationResult`를 생성하고 Engine이 동일 객체를 반환하도록 전환했다.
- CLI 직렬화 경계에서만 Decision을 기존 `companies[].score`와 `companies[].recommendation` JSON shape로
  투영해 외부 schema를 유지했다.
