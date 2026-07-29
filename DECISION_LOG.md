# 설계 결정 기록

## 사용 방법

이 문서는 반복적으로 참조할 중요한 설계 결정을 기록한다. 각 항목은 결정, 이유, 영향 범위를 포함한다. 구현 세부와 변경 이력은 해당 `docs/pr-*.md`에서 관리하며, 이 문서는 장기적으로 유효한 결론만 요약한다.

## D-001 — Domain과 외부 transport 분리

**결정:** 외부 provider와 LLM 응답은 transport DTO로 받고 Parser가 검증된 immutable Domain 모델로 변환한다.

**이유:** 외부 응답의 느슨한 타입과 모델 변동이 Policy/Workflow 계약을 훼손하지 않게 한다.

**영향:** Domain은 OpenAI SDK·LangGraph·CLI를 모르며, Parser가 type/range/index/enum 책임을 가진다.

## D-002 — LLM은 관측, Policy는 결정

**결정:** LLM은 event, score, 기사 관계, 근거 같은 관측만 반환하며 최종 상태·독립 출처·추천을 결정하지 않는다.

**이유:** 자연어 모델의 변동성과 설명을 deterministic business rule과 분리한다.

**영향:** Prompt에 정책 임계값을 넣지 않으며 screening/cross-validation/resolve/recommendation policy를 독립 테스트한다.

## D-003 — 부분 성공 우선

**결정:** item 또는 batch의 recover 가능한 오류는 정상 sibling과 후속 batch를 막지 않는다. 대상이 있었는데 유효 결과가 전혀 없을 때만 단계 예외를 낸다.

**이유:** 실제 LLM/외부 데이터는 부분적으로 malformed일 수 있으며, 하나의 오류가 전체 뉴스 처리 기회를 없애면 안 된다.

**영향:** parse result는 assessment와 제한된 error observation을 함께 반환한다. 가짜 0점 또는 fabricated evidence fallback은 만들지 않는다.

## D-004 — Mock과 OpenAI의 Workflow 계약 통일

**결정:** Mock과 OpenAI는 동일한 Workflow, downstream Policy, CLI JSON schema를 사용하고 관측 구현만 교체한다.

**이유:** 회귀 테스트는 재현 가능해야 하고, production 전환이 business logic 차이를 만들면 안 된다.

**영향:** bootstrap에서 mode별 구현을 주입하며 Mock은 기본 테스트 경로다.

## D-005 — OpenAI gateway 공유

**결정:** 현재 stateless structured-output LLM gateway는 Extractor, Screener, Cross Validator가 공유한다. AsyncOpenAI client와 structured client도 한 번만 만든다.

**이유:** 연결과 설정을 중앙화하면서 작업별 response model은 호출 인자로 분리할 수 있다.

**영향:** gateway가 response model, prompt 설정 같은 작업별 mutable state를 갖게 되면 shared client만 유지하고 작업별 gateway를 분리한다.

## D-006 — candidate ID는 내부 전용

**결정:** cross-validation candidate ID는 Parser 오류 상관관계와 내부 불변식에만 사용하고 prompt/LLM response에 보내지 않는다.

**이유:** 내부 workflow 구현을 외부 모델 계약에 노출하지 않고, 민감도와 coupling을 낮춘다.

**영향:** LLM batch는 local event/evidence index로 mapping하며 Parser가 candidate를 복원한다.

## D-007 — 독립 출처는 보수적 연결 요소

**결정:** URL domain 또는 normalized source가 같은 evidence는 같은 출처로 연결하고, 그 연결 요소 수를 독립 출처 수로 계산한다.

**이유:** 재배포 기사와 동일 source 표기를 여러 독립 근거로 과대계산하지 않는다.

**영향:** A-B source 일치와 A-C domain 일치는 A·B·C를 하나로 합친다. domain 정규화는 lowercase/port 제거/`www.` 제거까지만 하며 PSL 처리는 후속 개선이다.

## D-008 — 비식별 source 목록은 최소·정확 일치

**결정:** `unknown`, `unknown source`, `n/a`, `na`, `none`, `null`, `news`, `newsroom`만 기본 비식별 source로 취급한다.

**이유:** `publisher`, `media`, `press`, `source` 같은 일반 단어를 제외하면 정상 언론사 명칭을 잃을 수 있다.

**영향:** 부분 문자열이나 prefix matching을 금지한다. 새 값은 실제 운영 데이터에서 placeholder로 반복됨이 확인될 때만 추가한다.

## D-009 — 안전한 구조화 로그

**결정:** 운영 로그에는 제한된 index, internal ID, error kind만 남긴다.

**이유:** 기사 본문, prompt, SDK response, API key, 개인정보와 예외 전문의 노출을 막는다.

**영향:** 오류 관측 모델 자체에도 민감한 원문이나 무제한 문자열을 저장하지 않는다.
