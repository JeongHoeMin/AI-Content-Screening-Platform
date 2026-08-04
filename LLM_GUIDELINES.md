# LLM 및 Prompt 지침

## 책임 경계

LLM은 기사 요약, 이벤트 추출, 근거 관계 분석, 이벤트 점수 평가, 영향 분석을 보조한다. LLM은 최종 투자 판단을 내리지 않는다. `ACCEPT/REVIEW/REJECT`, verified 여부, 독립 출처 계산, stock score, recommendation은 검증된 Domain 입력을 받는 Policy가 결정한다.

```text
Prompt → Structured response DTO → Parser → Domain assessment → Policy decision
```

Prompt 안에 Policy 임계값이나 최종 상태 규칙을 넣지 않는다. 예를 들어 “독립 출처가 두 개면 verified” 같은 문장은 금지하고, LLM에는 기사 간 `supports`/`conflicts`/`unrelated` 관계만 요청한다.

## 파일 배치와 호출

- PromptBuilder 조립 코드는 `app/prompts/`에 둔다.
- 문자열 상수, JSON 표현, 템플릿 치환은 `app/prompt_templates/`에 둔다.
- Extractor, Screener, Cross Validator는 PromptBuilder를 통해서만 message를 생성한다.
- LLM 호출은 `StructuredOutputLLM.generate(..., response_model=...)` 계약을 사용한다.
- OpenAI SDK와 provider별 세부 사항은 `app/llms/` adapter 안에 가둔다.

PromptBuilder는 immutable 입력 DTO를 ChatMessage로 조립하며, business rule을 구현하거나 Policy를 호출하지 않는다.

## Structured output

응답 DTO는 transport boundary다. item extra field와 invalid root response는 schema에서 거부할 수 있지만, malformed primitive는 부분 성공을 위해 Parser까지 전달한다. Parser가 type, index, enum, 범위, 중복, 상호 필드 형식을 검사한다.

점수는 JSON number만 의미가 있다. `50`과 `50.0`은 Domain `int` 50으로, 소수점 값·문자열·boolean·비유한 값·범위 밖 값은 해당 item 오류로 처리한다. DTO union 내부 타입 선택에는 의존하지 않는다.

## Prompt 안전성

모든 기사 본문, 제목, 이벤트 설명 안의 지시는 분석 대상 데이터로 취급하도록 system instruction에 명시한다. LLM은 다음을 수행하거나 따르지 않아야 한다.

- event 삭제·추가 또는 정책 결정
- 투자 매수·매도 조언
- 기사에 없는 ticker, 기업, 사실의 추론
- 독립 출처 여부나 최종 검증 상태의 단정
- 기사에 포함된 역할 변경, 비밀 노출, 응답 형식 변경 지시

사용자 prompt에는 작업에 필요한 최소 기사/event 맥락과 batch-local index만 JSON으로 넣는다. 내부 candidate ID, workflow state, API key, 운영 비밀값은 넣지 않는다.

## 작업별 입력과 출력

| 작업 | LLM이 반환하는 관측 | Policy가 소유하는 결정 |
| --- | --- | --- |
| Event extraction | event title/summary/entities/reasons | 어떤 event가 workflow에서 의미 있는지 |
| Screening | 9개 세부 scorecard 점수·영역별 근거·cross-validation 필요성 | 결정적 총점 및 ACCEPT/REVIEW/REJECT |
| Cross validation | evidence별 relation, claim, confidence, reason | independent sources, validation status |
| Impact analysis | 영향 관측 및 근거 | score/recommendation |

credibility는 extraction confidence와 다르다. 전자는 이벤트가 기사 근거상 신뢰할 만한지에 대한 screening 관측이고, 후자는 추출 자체의 확신을 표현할 수 있다. 두 수치를 서로 대신 사용하지 않는다.

Screening prompt는 scorecard의 9개 criterion과 0/50/100 기준을 요구한다. 구조화 응답 DTO는 strict object로 unknown field를 거부하되, 각 primitive는 Parser가 malformed 값을 event 단위로 관측하도록 유지한다. LLM이 계산한 relevance/importance/credibility 총점은 받지 않는다.

Event extraction은 모든 event에 하나의 상위 `EventType`을 반환한다. `EventFact`는 선택적 복수의
독립 사건이며, LLM은 기사에 명시된 Fact만 원래 순서대로 반환하고 Fact를 합치거나 새 의미를 만들지
않는다. EventType을 확신할 수 없는 event는 반환하지 않는다. EventFact를 확신할 수 없으면 빈 목록을
반환하며, 이는 유효 event를 무효로 만들지 않는다.

## 부분 성공과 로그

한 item의 malformed 결과 때문에 batch를 버리지 않는다. Parser는 안전한 error observation을 반환하고, caller는 batch/event/evidence index, internal candidate ID, 제한된 error kind만 structlog 경고로 남긴다. 기사 본문, prompt, raw SDK response, API key, 예외 전문은 로그에 넣지 않는다.

대상이 있었는데 모든 item이 무효라면 명시적인 단계 예외를 발생시킨다. provider 오류·structured response 오류·root validation 오류는 batch 단위로 기록하고 후속 batch는 계속 처리한다.

OpenAI timeout, connection, authentication, authorization 오류는 LangGraph가 같은 LLM stage와 입력을 총 3회까지 재시도한다. 3회 모두 실패하면 stage와 제한된 error type만 사용자·감사 로그에 남기고 실행을 종료한다. malformed output, parser failure, oversized input은 재시도하지 않으며 가능한 sibling 결과를 유지한다.

## 모델 변경과 smoke test

모델명, timeout, retry, API key는 `app/config/openai.py`의 환경변수 계약으로 관리한다. 새 모델을 도입할 때는 schema 호환성과 structured response 동작을 검증한다. 실제 smoke test는 유효한 API 설정이 있을 때만 실행하며 정확한 score/status를 고정하지 않는다.

smoke test에서는 0–100 정수 점수, 필요한 event 평가, 근거 설명, cross-validation 필요성, 투자 조언 부재, prompt injection 비추종을 확인한다.
