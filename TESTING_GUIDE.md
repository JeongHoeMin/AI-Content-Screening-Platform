# 테스트 가이드

## 목표

테스트는 LLM의 특정 문장이나 점수를 맞히는 것이 아니라, transport boundary, Parser, Policy, Workflow, CLI의 결정적 계약을 고정한다. Mock mode와 OpenAI mode는 동일한 Workflow 및 최종 JSON schema를 유지해야 한다.

## 테스트 계층

| 계층 | 확인할 내용 |
| --- | --- |
| Domain/DTO | Pydantic schema, extra field, 필수 필드, JSON 경계 |
| Parser | 타입·범위·중복·누락·identity·순서·부분 성공 |
| Policy | LLM 관측과 독립적인 결정 규칙 |
| 서비스 | batching, 오류 격리, retry 경계, 예상 밖 오류 전파 |
| Workflow | 단계 연결, 누락된 부분 결과, event identity 불변식 |
| Bootstrap/CLI | mode 조립, shared gateway, 환경 설정, JSON schema/exit code |
| 수집 필터 | 테마·주제 AND, 빈 선택 호환, 제외 사유·원본 identity, 안전한 snapshot |

## Parser 테스트 규칙

Python 객체 검증과 `model_validate_json()` 검증을 모두 포함해 실제 JSON number와 문자열 number를 구분한다. `50`과 `50.0`은 최종 Domain score가 실제 `int` 50인지 검사한다. `50.5`, 문자열, boolean, `NaN`, `Infinity`, 범위 밖 값은 item 오류인지 검사한다.

중복·범위 밖·누락 index와 malformed sibling을 만들고 정상 sibling 결과가 입력 순서와 원본 object identity를 보존하는지 확인한다. cross validation은 event/evidence 수준 오류가 서로 격리되는지, relation과 claim 형식 규칙이 적용되는지도 검증한다.

## LLM 서비스 테스트 규칙

실제 API 대신 fake structured-output gateway를 기본으로 사용한다. 다음 경우를 반드시 다룬다.

- 빈 입력은 LLM 호출 없이 빈 결과다.
- 단일·다중 batch의 결과가 합쳐진다.
- provider, structured response, root validation 오류 뒤에도 다음 batch가 처리된다.
- item parser 오류는 정상 sibling을 막지 않는다.
- 입력이 있었지만 유효 결과가 하나도 없으면 명시적 예외가 발생한다.
- 예상 밖 RuntimeError와 object identity 위반은 전파된다.
- 경고 로그는 제한 필드만 가지며 기사 본문과 API key를 포함하지 않는다.

## Policy와 Workflow 테스트

Policy fake를 주입해 LLM 점수와 무관하게 Policy 결과만 사용되는지 확인한다. screening decision 일부가 누락되어도 Cross Validator와 Resolve가 남은 decision으로 완료되는지 확인한다. 독립 출처 계산은 domain/source 동등성, 연결 요소의 전이 병합, source fallback, 출처 불명 비가산, placeholder 정확 일치 규칙을 검증한다.

## OpenAI smoke test

실제 OpenAI smoke test는 API key가 명시적으로 제공된 경우에만 실행한다. 고정 score, confidence, status를 단정하지 않는다. 구조화 응답, 범위 내 정수 점수, 평가 근거, cross-validation 설명, 투자 조언 금지, prompt injection 비추종을 확인한다.

## 기본 검증 명령

```bash
uv run pytest
uv run python -m compileall app tests
git diff --check
```

네트워크, 비용, 비밀값이 필요한 테스트는 기본 전체 테스트에 섞지 않는다. 실행 방법과 필요한 환경변수는 별도 명시한다.

투자 테마·뉴스 주제 필터는 카탈로그 term, 선택 조건, 제외 이유와 catalog version을 단위 테스트한다. PostgreSQL
snapshot은 실행 조건과 집계만 저장하는지 검증하며 기사 원문·prompt가 저장 대상에 섞이지 않는지 확인한다.

정기 실행 테스트는 KST cron의 다음 UTC slot, 일/요일 cron 의미, schedule DB migration, due lease, Telegram 실패 격리, 설정 비밀번호·HttpOnly session 인증을 확인한다. Docker smoke에서는 migration 적용 후 `schedule-worker`가 PostgreSQL healthcheck 이후 기동하는지 확인한다.

## 추천 가격 테스트

기본 pytest는 외부 시세 API를 호출하지 않는다. KIS/KRX adapter의 fallback, 휴장일 lookback, 제한된 오류,
entry/latest snapshot identity, BUY/SELL 사후 비교, `가격 미확인`, UTC 저장과 KST 투영은 fake HTTP client로
검증한다. Compose 테스트는 KIS 설정 **이름**이 dashboard와 `schedule-worker`에 전달되는지만 확인하며 값을
기록하거나 출력하지 않는다.

실제 KIS 계약 확인은 로컬에서만 아래처럼 명시적으로 opt-in한다. `KIS_APP_KEY`와 `KIS_APP_SECRET`이 둘 다
없으면 skip되며, 기본 CI에는 이 환경 변수를 설정하지 않는다.

```bash
RUN_LIVE_MARKET_DATA_TESTS=1 uv run pytest tests/test_market_price_live_contract.py -q
```

이 live test는 삼성전자(`005930`)의 KIS 가격이 `AVAILABLE`이고 양수인지만 검사한다. credential, token,
authorization header, raw payload를 assertion·로그·출력에 포함하지 않는다.
