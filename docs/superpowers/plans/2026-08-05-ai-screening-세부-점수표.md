# AI Screening 세부 점수표 구현 계획

> **에이전트 작업자용:** REQUIRED SUB-SKILL: `superpowers:executing-plans`로 단계별 실행한다. 각 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** LLM이 관련성·중요도·신뢰도의 세부 항목을 0–100으로 관측하고, Parser가 이를 검증한 뒤 versioned 가중 평균으로 세 총점을 결정적으로 계산하도록 만든다.

**아키텍처:** transport DTO는 malformed primitive를 관측할 수 있는 strict object로 유지한다. Parser는 item 단위 부분 성공을 유지하며 세부 점수·근거를 검증하고 `ScreeningScorecard` Domain을 생성한다. `ScreeningScorecardPolicy`가 세 총점을 계산하며 기존 `ScreeningPolicy`는 계산된 총점만 사용한다.

**기술 스택:** Python 3.9 이상, Pydantic v2, OpenAI structured output, pytest.

## 전역 제약

- LLM은 세부 점수와 간결한 근거만 관측하며 ACCEPT/REVIEW/REJECT나 매수·매도 결정을 만들지 않는다.
- 세부 항목은 0–100 실제 정수이며 누락·중복·범위 밖·비정수 값은 해당 event만 제외한다.
- 총점은 versioned Policy의 가중 평균을 half-up 정수 반올림으로 계산한다.
- transport DTO는 `extra="forbid"`를 유지하고 type 없는 JSON schema node를 만들지 않는다.
- 기사 원문, prompt, raw LLM response는 로그·오류 객체·대시보드 결과에 추가하지 않는다.
- 설계·계획·운영 문서는 한국어로 작성한다.

---

## 파일 구조

| 파일 | 책임 |
| --- | --- |
| `app/models/screening.py` | scorecard Domain, strict transport DTO, parse error enum |
| `app/screeners/scorecard_policy.py` | versioned 가중치와 결정적 총점 계산 |
| `app/screeners/default_parser.py` | scorecard primitive 검증과 Domain 변환 |
| `app/screeners/policy.py` | 계산된 scorecard를 decision에 보존 |
| `app/prompt_templates/screening.py` | 세부 평가 기준·schema를 포함한 LLM 지시 |
| `app/web/app.py` / `app/web/dashboard_html.py` | 세부 점수와 합산 총점의 안전한 표시 |
| `tests/test_*screening*.py` | Domain, parser, aggregate, prompt, dashboard 회귀 |

## Task 1: Scorecard Domain과 결정적 합산 Policy

**Files:**
- Modify: `app/models/screening.py`
- Create: `app/screeners/scorecard_policy.py`
- Modify: `app/screeners/__init__.py`
- Test: `tests/test_screening_scorecard.py`

**Interfaces:**
- Produces: `ScreeningScorecard`, `ScorecardDimension`, `ScorecardCriterion`, `ScreeningScorecardPolicy.calculate(scorecard) -> ScreeningScorecard`.
- Consumes: 9개의 세부 점수와 dimension별 최대 1개 근거.

- [ ] **Step 1: 실패 테스트를 작성한다.**

```python
def test_scorecard_policy_calculates_weighted_relevance_total() -> None:
    scorecard = make_scorecard(theme_directness=100, topic_match=50, market_path=0)
    calculated = ScreeningScorecardPolicy().calculate(scorecard)
    assert calculated.relevance.total == 50
```

- [ ] **Step 2: 실패를 확인한다.**

Run: `uv run pytest -q tests/test_screening_scorecard.py::test_scorecard_policy_calculates_weighted_relevance_total`

Expected: `ImportError` 또는 scorecard API 부재로 실패한다.

- [ ] **Step 3: immutable scorecard와 exhaustive weight catalog를 구현한다.**

```python
class RelevanceCriterion(str, Enum):
    THEME_DIRECTNESS = "theme_directness"
    TOPIC_MATCH = "topic_match"
    MARKET_TRANSMISSION_PATH = "market_transmission_path"

class ScreeningScorecardPolicy:
    def calculate(self, scorecard: ScreeningScorecard) -> ScreeningScorecard:
        """Return a copied immutable scorecard with deterministic totals."""
```

관련성은 테마 직접성·주제 일치도·시장 전파 경로, 중요도는 영향 크기·범위/파급도·시간 민감도,
신뢰도는 출처 권위·근거 구체성·교차 확인/불확실성으로 구성한다. 각 dimension의 weight는 합계 1.0이며
catalog validator가 누락·중복·범위 밖을 fail-fast한다.

- [ ] **Step 4: 경계·반올림·catalog 테스트를 통과시킨다.**

Run: `uv run pytest -q tests/test_screening_scorecard.py`

Expected: 가중 평균, 0/100, half-up 반올림, 누락 criterion catalog 거부가 통과한다.

- [ ] **Step 5: 커밋한다.**

```bash
git add app/models/screening.py app/screeners/scorecard_policy.py app/screeners/__init__.py tests/test_screening_scorecard.py
git commit -m "feat: define deterministic screening scorecards"
```

## Task 2: Structured DTO와 Parser 부분 성공

**Files:**
- Modify: `app/models/screening.py`
- Modify: `app/screeners/default_parser.py`
- Test: `tests/test_llm_event_screener.py`

**Interfaces:**
- Consumes: `ScreeningAssessmentResponseItem.scorecard` with primitive score fields.
- Produces: `ScreeningAssessment(scorecard=...)` or `INVALID_SCORECARD` error for only that event.

- [ ] **Step 1: malformed scorecard가 sibling assessment를 보존하는 실패 테스트를 작성한다.**

```python
def test_parser_excludes_only_item_with_missing_scorecard_criterion() -> None:
    result = parser.parse(response_with_one_valid_and_one_missing_criterion, candidates)
    assert [assessment.candidate_id for assessment in result.assessments] == [candidates[0].candidate_id]
    assert result.errors[0].kind is ScreeningParseErrorKind.INVALID_SCORECARD
```

- [ ] **Step 2: 실패를 확인한다.**

Run: `uv run pytest -q tests/test_llm_event_screener.py::test_parser_excludes_only_item_with_missing_scorecard_criterion`

Expected: scorecard field 또는 error kind가 없어 실패한다.

- [ ] **Step 3: strict DTO와 Parser를 구현한다.**

`ScorecardResponseItem`은 각 세부 score와 dimension reason을 explicit field로 선언하고 `extra="forbid"`를
사용한다. Parser는 9개 score의 number/int/range 규칙, nonblank reason, 무결한 criterion set을 검사한 뒤
Policy로 계산한 scorecard를 Assessment에 넣는다. 기존 top-level score transport field는 제거하고 totals는
LLM이 입력하지 않는다.

- [ ] **Step 4: Parser와 schema 회귀 테스트를 통과시킨다.**

Run: `uv run pytest -q tests/test_llm_event_screener.py tests/test_openai_structured_output.py`

Expected: valid sibling 보존, malformed item 제외, strict extra field 거부, schema primitive 계약이 통과한다.

- [ ] **Step 5: 커밋한다.**

```bash
git add app/models/screening.py app/screeners/default_parser.py tests/test_llm_event_screener.py tests/test_openai_structured_output.py
git commit -m "feat: parse detailed screening scorecards"
```

## Task 3: Prompt·Policy·Dashboard Projection

**Files:**
- Modify: `app/prompt_templates/screening.py`
- Modify: `app/screeners/policy.py`
- Modify: `app/web/app.py`
- Modify: `app/web/dashboard_html.py`
- Test: `tests/test_screening_policy.py`, `tests/test_web_dashboard.py`, `tests/test_evaluator_prompt_builder.py`

**Interfaces:**
- Consumes: calculated `ScreeningAssessment.scorecard`.
- Produces: existing total scores plus display-safe sub-score rows and per-dimension reason.

- [ ] **Step 1: prompt와 dashboard contract 실패 테스트를 작성한다.**

```python
def test_screening_prompt_requires_all_nine_scorecard_criteria() -> None:
    prompt = build_screening_system_prompt()
    assert "theme_directness" in prompt
    assert "source_authority" in prompt
```

- [ ] **Step 2: 실패를 확인한다.**

Run: `uv run pytest -q tests/test_evaluator_prompt_builder.py::test_screening_prompt_requires_all_nine_scorecard_criteria`

Expected: criterion 문자열이 없어 실패한다.

- [ ] **Step 3: prompt와 projection을 구현한다.**

프롬프트는 9개 항목의 0/50/100 기준, criterion별 점수, dimension reason을 요구하고 Policy 임계값을 포함하지
않는다. `ScreeningDecision`은 same scorecard를 보존한다. Dashboard는 합산 3점과 세부 9점/근거를 표시하지만
LLM raw output·prompt는 표시하지 않는다.

- [ ] **Step 4: Policy·prompt·dashboard 회귀를 통과시킨다.**

Run: `uv run pytest -q tests/test_screening_policy.py tests/test_evaluator_prompt_builder.py tests/test_web_dashboard.py`

Expected: 기존 ACCEPT/REVIEW/REJECT threshold가 calculated total을 사용하고 scorecard UI contract가 통과한다.

- [ ] **Step 5: 커밋한다.**

```bash
git add app/prompt_templates/screening.py app/screeners/policy.py app/web/app.py app/web/dashboard_html.py tests/test_screening_policy.py tests/test_evaluator_prompt_builder.py tests/test_web_dashboard.py
git commit -m "feat: expose detailed screening scorecards"
```

## Task 4: 문서·전체 검증·PR

**Files:**
- Modify: `PROJECT_GUIDE.md`, `ARCHITECTURE.md`, `DOMAIN_MODEL.md`, `LLM_GUIDELINES.md`, `WORKFLOW.md`, `TESTING_GUIDE.md`, `ROADMAP.md`, `DECISION_LOG.md`
- Create: `docs/pr-48-ai-screening-scorecards.md`
- Test: `tests/test_documentation_contract.py`

- [ ] **Step 1: 문서 계약 실패 테스트를 작성한다.**

```python
def test_domain_docs_describe_deterministic_screening_scorecard() -> None:
    document = Path("DOMAIN_MODEL.md").read_text(encoding="utf-8")
    assert "세부 점수표" in document
    assert "결정적" in document
```

- [ ] **Step 2: 실패를 확인한다.**

Run: `uv run pytest -q tests/test_documentation_contract.py::test_domain_docs_describe_deterministic_screening_scorecard`

Expected: assertion failure가 발생한다.

- [ ] **Step 3: 한국어 문서를 갱신한다.**

각 문서에 LLM 관측/Parser/scorecard policy 경계, 9개 criterion, versioned aggregate, 부분 성공과 schema
제약을 기록한다. ADR에는 LLM total score를 신뢰하지 않고 Policy가 산출한다는 결정을 기록한다.

- [ ] **Step 4: 전체 검증을 실행한다.**

Run: `uv run pytest && uv run python -m compileall app tests && git diff --check`

Expected: 전체 테스트, 컴파일, diff check가 성공한다.

- [ ] **Step 5: 커밋·푸시·PR을 만든다.**

```bash
git add PROJECT_GUIDE.md ARCHITECTURE.md DOMAIN_MODEL.md LLM_GUIDELINES.md WORKFLOW.md TESTING_GUIDE.md ROADMAP.md DECISION_LOG.md docs/pr-48-ai-screening-scorecards.md tests/test_documentation_contract.py
git commit -m "docs: record AI screening scorecards"
git push -u origin codex/screening-scorecard
gh pr create --base main --head codex/screening-scorecard --title "feat: AI Screening 세부 점수표"
```

## 계획 자체 점검

- 구조화 출력 제한 검토와 개선은 Task 2의 strict DTO/schema test로 다룬다.
- 세 평가 영역의 세부 항목과 결정적 합산은 Task 1에서 정의하고 Task 2·3에서 workflow 전체에 연결한다.
- LLM이 관측만 하고 Parser·Policy가 검증·총점·결정을 소유하는 기존 헌법을 유지한다.
- 과거 실행/재시도, 워크플로우 그래프, KST schedule·Telegram, 가격 성과는 별도 승인 PR로 남긴다.
