# PR33: Ranking & Candidate Selection v1

## Summary

PR32는 `RecommendationDecision`에 score, action, action reason, threshold snapshot을 감사 가능한
immutable Domain 값으로 보존했다. 그러나 현재 결과는 어떤 `STRONG_BUY`와 `BUY`를 실제 매수 후보로
선택할지, 후보가 아닌 decision은 왜 제외됐는지를 표현하지 않는다.

PR33은 Recommendation action과 score를 변경하지 않고 각 `RecommendationDecision`을 결정적으로
평가해 **후보 우선순위와 선택 여부를 설명 가능한 Domain 결과로 보존**한다. Candidate Selection은
scoring을 재수행하거나 `ScoreContribution`, evidence, `CompanyImpact`를 읽거나 재해석하지 않는다.

## Scope

- immutable Pydantic `RecommendationRankEntry`, exhaustive `RecommendationRankCatalog`,
  `RankingPolicyConfig`, `CandidateEvaluation`, `CandidateSelectionResult`를 추가한다.
- `STRONG_BUY`와 `BUY`를 기본 eligible action으로, 나머지 세 action을 not eligible로 명시한다.
- action priority, score descending, input index ascending의 stable deterministic ordering을 적용한다.
- 선택·비선택·limit 초과 사유와 selected rank를 immutable evaluation에 보존한다.
- Candidate Selection Policy가 final result를 만들고 Engine이 동일 객체를 그대로 반환하도록 한다.
- Bootstrap, Domain/Workflow/Architecture/ADR/Roadmap, PR33 문서 및 regression test를 갱신한다.

## Non Goals

- score 재계산, score cap/normalization, action·reason·threshold 변경
- `ScoreContribution`, evidence, `CompanyImpact`, validation, uncertainty의 재해석
- portfolio allocation, position sizing, top-level investment amount, automatic order
- market data, risk/confidence weighting, user profile별 policy, LLM 호출
- 현재 CLI JSON schema에 candidate status, rank, reason code, ranking policy version 추가

## Approved Product Decisions

### 1. Exhaustive ranking catalog

`RecommendationRankEntry`는 하나의 action에 대한 ranking policy 사실이다.

```text
RecommendationRankEntry
├── action: RecommendationAction
├── eligible: bool
└── priority: int
```

`RecommendationRankCatalog`는 immutable Pydantic registry이며 `entries` tuple만 저장한다. Catalog는
`RecommendationAction`의 다섯 값을 정확히 한 번씩 포함해야 한다. duplicate/missing action, negative
priority, duplicate priority는 생성 시 fail-fast한다. priority는 table 전체에서 유일하므로 동일 action
priority가 아닌 다른 action priority가 deterministic key를 숨기지 않는다.

v1 default catalog는 다음과 같다.

| Action | Eligible | Priority |
| --- | --- | --- |
| `STRONG_BUY` | true | 0 |
| `BUY` | true | 1 |
| `HOLD` | false | 2 |
| `SELL` | false | 3 |
| `STRONG_SELL` | false | 4 |

비eligible action의 priority도 catalog 완전성 및 교체 가능성을 위해 등록하지만, v1 sort 대상은 아니다.

### 2. Policy configuration

`RankingPolicyConfig`는 immutable Pydantic 정책의 유일한 입력이다.

```text
RankingPolicyConfig
├── policy_version: str
├── max_candidates: int
└── catalog: RecommendationRankCatalog
```

- blank `policy_version`과 `max_candidates < 1`은 Config 생성 시 fail-fast한다.
- Catalog는 Config에 포함되는 유일한 ranking policy source다. Strategy/Policy/Engine은 action mapping,
  priority, candidate limit을 hard-code하지 않는다.
- Bootstrap은 default config 하나를 생성하고 Mock/OpenAI workflow에 동일 instance를 주입한다.

### 3. Candidate evaluation and result

```text
CandidateEvaluation
├── decision: RecommendationDecision
├── status: CandidateStatus
├── reason_code: CandidateReasonCode
├── input_index: int
└── rank: int | None

CandidateSelectionResult
├── policy_version
└── evaluations: tuple[CandidateEvaluation, ...]
```

`CandidateStatus`는 `SELECTED`, `NOT_ELIGIBLE`, `OUTSIDE_LIMIT` 세 값이다. `CandidateReasonCode`는 다음
값을 가진다.

| Status / Action | Reason code |
| --- | --- |
| selected `STRONG_BUY` | `SELECTED_STRONG_BUY` |
| selected `BUY` | `SELECTED_BUY` |
| not eligible `HOLD` | `EXCLUDED_HOLD` |
| not eligible `SELL` | `EXCLUDED_SELL` |
| not eligible `STRONG_SELL` | `EXCLUDED_STRONG_SELL` |
| eligible but over limit | `EXCLUDED_OUTSIDE_CANDIDATE_LIMIT` |

`CandidateEvaluation` validator는 status, action, reason code, rank 조합을 fail-fast한다.

- `SELECTED`는 rank `>= 1`을 반드시 가진다.
- `NOT_ELIGIBLE`과 `OUTSIDE_LIMIT`은 rank를 가질 수 없다.
- `SELECTED`는 eligible action과 해당 selected reason만 가진다.
- `NOT_ELIGIBLE`은 catalog상 비eligible action의 action별 excluded reason만 가진다.
- `OUTSIDE_LIMIT`은 eligible action과 `EXCLUDED_OUTSIDE_CANDIDATE_LIMIT`만 가진다.

`CandidateSelectionResult`만 ranking policy version을 보존한다. result는 다음 read-only property를
제공하며 별도 tuple을 저장하지 않는다.

- `candidates`: `SELECTED` evaluation을 rank ascending으로 반환한다.
- `excluded`: SELECTED가 아닌 evaluation을 `input_index` ascending으로 반환한다.
- `decisions`: 전체 `RecommendationDecision`을 input index 순서와 object identity 그대로 반환한다.

### 4. Policy ordering and selection

`CandidateSelectionPolicy`는 `RecommendationResult`의 모든 Decision에 정확히 하나의
`CandidateEvaluation`을 만든다. input Decision을 복사·교체하지 않으며 score/action을 수정하지 않는다.

1. Catalog entry가 eligible인 Decision만 후보 sort 대상으로 만든다.
2. deterministic key `(action priority ascending, score descending, input_index ascending)`로 stable sort한다.
3. 앞의 `max_candidates`개를 `SELECTED`로 지정하고 1부터 rank를 부여한다.
4. 남은 eligible Decision은 `OUTSIDE_LIMIT`으로 지정한다.
5. 비eligible Decision은 input index에 해당하는 `NOT_ELIGIBLE` evaluation을 만든다.

Evaluation storage order는 input Decision order다. ranking order는 `candidates` property만 통해 명시적으로
노출하므로 input provenance와 candidate priority를 혼동하지 않는다.

### 5. Engine, bootstrap, and CLI boundary

```text
RecommendationResult
    ↓
CandidateSelectionPolicy(config)
    ↓
CandidateSelectionResult(evaluations + policy_version)
    ↓
DefaultCandidateSelectionEngine
    ↓
same CandidateSelectionResult identity
```

- Policy가 final immutable `CandidateSelectionResult`를 생성한다.
- Engine은 configured Policy를 정확히 한 번 호출하고 반환된 result를 수정·복사·재조립·정렬·filtering하지
  않고 동일 identity로 반환한다.
- Bootstrap은 Mock/OpenAI workflow에 동일 default `RankingPolicyConfig` instance를 주입한다.
- Candidate Selection은 workflow의 internal Domain 결과로 보존한다. PR33의 CLI projection은 현재
  recommendation JSON contract를 변경하지 않으며 candidate provenance를 외부에 노출하지 않는다.

## Test Plan

### Domain and config

- Catalog가 다섯 action을 모두 포함하는지, duplicate/missing action을 reject하는지 검증한다.
- negative 또는 duplicate priority를 reject하고 default mapping을 검증한다.
- blank policy version과 `max_candidates < 1`을 reject하는지 검증한다.
- CandidateEvaluation의 status/reason/action/rank 모순을 fail-fast하는지 검증한다.
- Result properties가 candidate rank, excluded input index, all decision input index 및 original Decision identity를
  정확히 보존하는지 검증한다.

### Policy, engine, and regression

- `STRONG_BUY`/`BUY`의 eligible mapping과 `HOLD`/`SELL`/`STRONG_SELL`의 action별 exclusion mapping을 검증한다.
- action priority, score descending, input-index tie-break 및 같은 action/score의 deterministic order를 검증한다.
- `max_candidates` 초과 eligible Decision이 `OUTSIDE_LIMIT`이 되는지 검증한다.
- 모든 input Decision에 하나의 evaluation이 생성되고 빈 RecommendationResult가 빈 selection result를 만드는지
  검증한다.
- Policy version 보존, Policy가 original Decision identity를 보존하는지, Engine이 동일 Result identity를
  반환하며 한 번만 호출하는지 검증한다.
- Recommendation action/score 및 현재 CLI JSON schema가 PR33 이후에도 동일한지 workflow/CLI regression으로
  검증한다.
- `uv run pytest`, `uv run python -m compileall app tests`, `git diff --check`를 실행한다.

## Documentation Updates

- `ROADMAP.md`: PR33 완료 후 explainable recommendation 다음 단계의 candidate ranking 산출물을 반영한다.
- `DOMAIN_MODEL.md`: rank catalog/config, evaluation invariants, result projection 계약을 기록한다.
- `WORKFLOW.md`: Recommend 이후 Candidate Selection node와 identity contract를 기록한다.
- `ARCHITECTURE.md`: ranking policy의 dependency injection 및 CLI boundary를 추가한다.
- `DECISION_LOG.md`: deterministic candidate ranking과 external CLI projection 분리를 ADR로 기록한다.

## Proposed Commit Message

```text
feat: add deterministic candidate selection
```

## Change Log

### 2026-07-30 — Initial approved implementation plan

- PR32의 final `RecommendationDecision`을 유일한 입력으로 소비하는 deterministic candidate selection을 정의했다.
- action priority, score, input order를 명시적 stable sort key로 고정하고, selected/excluded provenance를
  atomic evaluation으로 보존하도록 했다.
- scoring 재해석, action 변경, portfolio allocation, risk/market data, CLI schema 변경은 후속 범위로 제한했다.

### 2026-07-30 — Contract consolidation

- `RecommendationResult.decisions`만 Candidate Selection의 입력이며, score와 recommendation action은
  selection 과정에서 변경하지 않는다는 범위를 다시 고정했다.
- `CandidateSelectionResult`가 ranking policy version의 유일한 소유자이고, `candidates`, `excluded`,
  `decisions`는 evaluations에서 계산되는 read-only projection임을 명시했다.
- Catalog 전수성·priority 유일성, evaluation status/reason/rank 불변식, stable sort key, max-candidate
  처리 및 Engine 동일-result identity를 구현 전 acceptance contract로 통합했다.
- CLI에는 candidate provenance를 추가하지 않고, 기존 Recommendation 결과·workflow 순서·JSON schema를
  회귀 검증 대상으로 유지한다.

### 2026-07-30 — Implementation completed

- immutable Candidate Selection Domain, exhaustive ranking catalog/config, stable sort Policy 및 transparent
  Engine identity contract를 구현했다.
- workflow의 Recommend 다음에 internal Candidate Selection node를 연결하고, CLI projection에서 해당 result를
  제외해 외부 JSON schema를 유지했다.
- Python 3.9 환경에서 config package import order에 따라 발생하던 resolver/config cycle은 directory config의
  lazy export로 분리해 candidate package의 독립 import도 보장했다.

### 2026-07-30 — Eligibility contract hardening

- `eligible`은 v1 제품 정책을 명시·검증하는 Catalog 사실로 고정했다. STRONG_BUY/BUY 외 action의 eligibility
  변경과 BUY/STRONG_BUY의 exclusion은 Catalog 생성 시 fail-fast한다.
- priority만 교체 가능한 ranking 요소로 제한하고, action별 selected/not-eligible reason은 Domain helper로
  단일화해 Policy와 Evaluation validator의 정책 중복을 제거했다.
- `ScreeningResult.candidate_selection`을 internal workflow의 필수 snapshot으로 고정했다. CLI JSON은
  candidate selection을 포함하지 않는 output projection이며 internal Result 역직렬화 DTO로 취급하지 않는다.
- workflow selector 호출·input recommendation identity·output selection identity 및 bootstrap engine type을
  회귀 테스트로 고정했다.
