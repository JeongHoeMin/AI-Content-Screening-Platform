# PR-27 OpenAI 뉴스 이벤트 심사기

## 요약

OpenAI 모드는 기존 결정적 심사 정책이 수락·검토·거절을 결정하기 전에 structured LLM output으로
추출된 뉴스 이벤트를 평가한다. Mock 모드와 공개 CLI JSON schema는 변경하지 않는다.

## 계약

LLM은 batch 지역 `event_index`, 관련성, 중요도, 신뢰도, 교차 검증 필요 여부, 간결한 이유를 반환한다.
점수는 JSON 숫자만 사용한다. 정수와 정수값 실수는 기존 0--100 도메인 정수 점수로 변환한다.
Parser는 이벤트 identity와 입력 순서를 복원하고 최종 결정은 Policy만 내린다.

`credibility`는 제공된 기사 근거와 출처 품질을 평가하며, 추출 지원 여부를 나타내는 extractor의
`confidence`와 다르다.

## 실패 및 관측 정책

잘못된 개별 평가는 가짜 fallback 점수 없이 제외한다. Parser는 구조화된 비민감 오류 관측값을 반환하고
Screener는 batch index, event index, 내부 candidate ID, 오류 종류만 로그에 남긴다.
기사 본문, prompt, 원시 provider 응답, API key는 로그에 남기지 않는다.
Provider·응답 batch 실패가 뒤 batch를 중단시키지 않으며, 입력 이벤트가 있는데 유효 결정이 하나도 없으면
`NoValidScreeningDecisionsError`를 발생시킨다.

## OpenAI 조립과 smoke test

Extractor와 Screener는 OpenAI structured-output client를 공유한다. 현재 structured LLM gateway는
요청별로 response model을 받으므로 공유해도 안전하다. 이후 stateful gateway가 생기면 client는 공유하되
task별 gateway 인스턴스를 생성한다.

자동 검증은 `uv run pytest`, `uv run python -m compileall app tests`, `git diff --check`를 사용한다.
유효한 OpenAI 설정이 있으면 다음을 실행한다.

```bash
uv run screening --mode openai --input examples/openai-screening-articles.json
```

정수 점수, 근거 기반 이유, 적절한 교차 검증 설명, 투자 조언 부재, prompt injection 텍스트에 대한 저항성을 확인한다.

## 구현 기록

### 2026-07-29

- response boundary는 정수값·0--100 검증을 Parser가 소유하도록 해 하나의 잘못된 점수가 정상 sibling을 버리지 않게 한다.
- Response DTO index는 strict integer이지만 음수가 아닌 값으로 제한하지 않는다. Parser는 음수·범위 밖 index를
  이벤트 단위 관측값으로 기록하고 정상 sibling을 보존한다.
- transport DTO는 malformed primitive를 보존해 Parser가 field 단위 오류를 기록하게 한다.
  Provider 호출, structured-output 응답 실패, 잘못된 응답 root는 batch-level 실패이고,
  field type·index·score·flag·reason은 event-level 실패다.
- 문자열·boolean·null event index는 `INVALID_EVENT_INDEX`로 기록한다. 실제 candidate에 매핑할 수 없으므로
  `candidate_id`는 `None`으로 남긴다.
