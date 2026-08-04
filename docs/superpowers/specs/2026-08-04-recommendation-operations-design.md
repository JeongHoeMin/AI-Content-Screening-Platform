# 추천 운영 기능 설계

## 상태

2026-08-04 사용자 승인.

## 목표

1. 추천 실행에서 반도체·AI·대체에너지 같은 투자 테마와 뉴스 주제를 함께 선택해 수집 문서를 필터링한다.
2. Parser가 소유하는 부분 성공 검증은 유지하면서 LLM 구조화 응답 계약을 강화한다.
3. AI Screening이 세부 평가 항목을 점수화하고, 관련성·중요도·신뢰도 총점을 결정적으로 계산한다.
4. 최근 4개 금요일을 대상으로 실행당 최대 25건의 입력 문서로 실제 OpenAI 실행을 수행하고, 안전한 진단 정보와 BUY/SELL 추천·조회 가능한 가격을 저장하며 실제 장애에 근거해 LangGraph 재시도 정책을 보완한다.
5. 대시보드의 선형 진행 목록을 노드·간선·재시도 전환을 보여 주는 실시간 워크플로우 그래프로 교체한다.
6. 한국시간 cron 설정과 실행 조건을 PostgreSQL에 저장하고 Docker worker가 실행하게 하며, 안전한 Telegram 요약, 매수/매도 추천 시점 가격, 성과 통계, 현재 평가손익을 제공한다.

## 공통 결정

- 사용자가 보는 시간은 항상 `Asia/Seoul`이다. 저장 시각은 UTC로 보존하고 UI·스케줄·보고 경계에서 명시적으로 시간대를 변환한다.
- 설계, 목표, 구현 계획, 운영 안내 문서는 한국어로 작성한다. 코드 식별자와 외부 API 환경변수 이름만 원문 표기를 유지한다.
- 과거 진단 실행은 실제 OpenAI 통합을 사용하며 실행당 최대 25건으로 제한한다. 이는 분석 실행이며 거래 지시가 아니다.
- LLM은 관측값만 반환한다. Parser가 전송 DTO를 검증하고, Policy는 `ACCEPT`·`REVIEW`·`REJECT`, 검증 상태, 점수, 추천 결정을 계속 소유한다.
- 기사 원문, 프롬프트, 자격 증명, 원시 provider 응답, 무제한 예외 문자열은 SSE, audit JSONL, Telegram, 로그에 포함하지 않는다.
- Worker가 소유하는 adapter만 DB 쓰기, Telegram 전송, 가격 스냅샷을 수행한다. Provider·Parser·Policy·Workflow Domain 노드는 DB나 Telegram을 직접 호출하지 않는다.

## 전달 구조

각 항목은 독립 브랜치와 PR로 진행하며, 병합 전 최신 선행 브랜치 기준으로 rebase한다.

1. `codex/collection-filters` — 투자 테마/뉴스 주제 필터 모델, 대시보드 요청 검증, provider 조회 조건 조립, 실행 필터 스냅샷 영속화.
2. `codex/screening-scorecard` — 구조화 출력 DTO 점검, 명시적 점수표, Parser 검증, 결정적 총점 계산, 프롬프트, Policy 호환성.
3. `codex/historical-retry-analysis` — 날짜 지정 실행 요청, 네 번의 금요일 OpenAI 진단, 실행·추천·조회 가능한 가격 스냅샷 영속화, 실패 보고서, 일시적 장애로 제한한 재시도 정책.
4. `codex/workflow-graph-dashboard` — 실시간 그래프 투영, 재시도 간선, 상태 전환, 접근 가능한 대시보드 렌더링.
5. `codex/scheduled-telegram-runs` — 스케줄/설정 영속화, 한국시간 cron worker, 실행 lease와 멱등성, Telegram adapter, 설정 페이지, 운영 문서.
6. `codex/recommendation-performance` — 추천 가격 스냅샷 adapter, 불변 성과 원장, 평가손익 통계, 대시보드 수익률 표시.

## 1. 수집 필터

`CollectionFilter`는 다음을 담는 immutable Domain 입력이다.

- 0개 이상의 투자 테마 enum(초기값: 반도체, AI, 대체에너지)
- 0개 이상의 뉴스 주제 enum
- KST 날짜 범위, 카테고리, 출처 목록, 최대 입력 건수
- 수동/예약 실행과 함께 직렬화하는 안정적인 필터 스냅샷

각 차원이 비어 있으면 해당 차원의 제한이 없다는 뜻이다. 두 차원이 모두 비어 있지 않으면 문서는 선택한 투자 테마와 선택 뉴스 주제 중 하나를 **모두** 만족해야 한다. 투자 테마 일치는 자유 입력 문자열이나 LLM 추론이 아닌, 테마별 산업어·제품어·대표 기업 alias·종목 코드를 명시한 버전 관리된 결정적 catalog로 처리한다. 뉴스 주제 일치도 같은 방식으로 Policy/configuration이 소유하는 결정적 분류기로 처리한다. catalog에 없는 표현은 억지로 일치시키지 않고 제외 사유와 catalog 버전을 기록한다.

Naver는 계속 전문 분석용이 아닌 탐색용 출처다. 전문 분석 가능 출처는 공식 DART와 설정된 IR RSS 문서다. 필터는 정규화 이후, Article 평가 및 추출 이전에 적용하며 제외 사유를 명시적으로 기록한다.

## 2. 구조화 출력과 Screening 점수표

현재의 엄격한 Pydantic root DTO는 알 수 없는 필드를 거부하지만, 복구 가능한 malformed 값을 관측하기 위해 primitive union을 사용한다. 이 특성은 전송 경계에만 유지한다. 현재의 문제는 세 개의 불투명 점수와 자유 형식 이유만으로는 총점의 근거를 감사할 수 없다는 점이다.

각 assessment는 고정된 세 가지 점수표를 반환하며, 각 세부 항목은 0–100점이다.

| 총점 | 세부 평가 항목 | 결정적 합산 방식 |
| --- | --- | --- |
| 관련성 | 선택 테마 직접성, 선택 뉴스 주제 일치도, 시장 전파 경로 | 버전 관리 가중 평균 후 정수 반올림 |
| 중요도 | 예상 영향 크기, 범위/파급도, 시간 민감도 | 버전 관리 가중 평균 후 정수 반올림 |
| 신뢰도 | 출처 권위, 근거 구체성, 교차 확인/불확실성 | 버전 관리 가중 평균 후 정수 반올림 |

LLM은 모든 고정 필드와 점수표별 간결한 근거 하나를 반환해야 한다. Parser는 누락·중복·정수가 아님·범위 초과·세부 항목 불일치를 해당 event에만 적용해 제외한다. Policy는 결정적으로 계산된 총점만 입력으로 받아 기존 임계값을 유지한다. 응답 모델은 strict object(`extra="forbid"`), 길이가 제한된 목록, 명시적 primitive type만 사용하고 `object`나 type 없는 JSON schema node를 두지 않는다. 최종 프롬프트는 생성된 JSON schema를 포함하되 Policy 임계값을 중복하지 않는다.

## 3. 과거 실행과 재시도

`RecommendationExecutionRequest`에 명시적인 KST 기준일과 최대 입력 문서 수를 추가한다. Run Harness는 기준일을 출처별 UTC 구간으로 변환하고 immutable 요청 스냅샷을 저장하며, stage별 시도를 안전한 식별자와 오류 종류로 기록한다.

초기 진단 대상은 실행 시점 이전의 최근 4개 금요일이다. 각 날짜는 실제 OpenAI 모드와 최대 25개의 선택 문서로 실행한다. 필요하다면 결정적 필터링을 만족하기 위한 초과 수집만 허용한다. 각 실행은 실행 요청·필터 snapshot·안전한 stage 시도 이력·추천 결정을 DB에 저장한다. BUY/SELL 추천은 시장가격 adapter가 해당 기준일의 거래 가능 가격을 반환할 때 entry price snapshot도 함께 저장하고, 가격을 얻지 못하면 명시적 `unavailable` 상태와 제한된 오류 종류만 저장한다. 결과 보고서는 기사 수락/제외 수, malformed 응답 수, 실패 batch, 재시도 횟수, 추출/canonical event, screening 결정, 미해결 기업, 추천, 가격 저장 성공/미확인 수를 포함한다. 기사 원문과 프롬프트는 절대 포함하지 않는다.

재시도 규칙은 이 보고서에 근거한다.

- OpenAI timeout, connection, rate-limit, service-unavailable 같은 일시적 오류는 LangGraph 노드에서 제한된 지수 backoff로 재시도한다.
- 일시적인 수집/시장가격 transport 오류는 Harness-owned adapter가 재시도하며, 다른 출처의 부분 성공을 보존한다.
- malformed structured output, Policy 제외, 입력 품질 실패, 잘못된 자격 증명은 재시도하지 않는다.
- 모든 재시도는 그래프 이벤트와 안전한 시도 기록을 남겨 대시보드에서 재시도 간선을 보이게 한다.

## 4. 실시간 워크플로우 그래프

대시보드 그래프는 collect, directory snapshot, evaluate, extract, deduplicate, screen, cross-validate, resolve, analyze, aggregate, score, recommend, candidate selection, terminal completion/failure 노드를 가진다. 방향 간선은 정상 진행을 보이며, 재시도 가능 노드는 현재 시도/최대 시도를 표시하는 라벨이 달린 back-edge를 가진다.

SSE는 graph node ID, transition ID, 안전한 수, 시도 횟수, 시각만 전달한다. 브라우저는 live graph state를 유지하고 원문·프롬프트를 노출하지 않은 채 pending, active, retrying, succeeded, skipped, failed 상태를 렌더링한다. 기존 뉴스 카드와 결과 표는 그래프 아래에 유지한다.

## 5. 예약 실행과 Telegram

DB는 활성 상태, 5필드 cron 표현식, `Asia/Seoul` timezone, 수집 필터 스냅샷, 25/50/100 입력 제한, 알림 설정, 마지막 실행 상태, optimistic schedule version을 가진 `ScheduledRecommendationJob`을 저장한다. 설정 페이지는 Harness API를 통해 이 모델을 검증하고 저장한다.

전용 Docker worker는 due job을 조회하고 DB lease를 얻은 후, 영속 실행을 생성하고 다음 실행 시각을 원자적으로 갱신한다. 이는 worker 재시작 이후 중복 실행을 막는다. Worker는 대시보드와 같은 Run Harness를 호출하며 system crontab을 수정하지 않는다. Telegram은 durable execution과 추천 기록이 생성된 뒤에만 전송한다. Telegram credential은 환경변수로만 주입하며 PostgreSQL이나 브라우저에 저장하지 않는다.

한국어 Telegram 요약에는 예약 시각, 필터 요약, 완료 상태, 안전한 집계, BUY/SELL 후보, Policy reason code, 점수, 진입 가격, 실행 ID/링크를 포함한다. 별도 운영 가이드는 bot token, chat ID, timezone, Docker worker, schedule, 장애 대응 설정을 설명한다.

## 6. 추천 성과

Harness는 BUY와 SELL 추천마다 실행 시점 가격 스냅샷을 저장한다. 스냅샷은 canonical 기업 ID, 종목 코드, action, KST 관측 시각, 출처, 통화, 거래일, 종가/최근 거래 가능 가격을 가진다. 시장 가격 adapter가 출처별 조회를 소유하며, 가격을 얻지 못하면 값을 만들어 내지 않고 명시적 안전 상태를 저장한다.

성과 조회는 같은 adapter로 최신 거래 가능 가격을 얻어 결정적으로 계산한다.

- BUY: `(최신가 - 진입가) / 진입가 * 100`
- SELL: `(진입가 - 최신가) / 진입가 * 100`

대시보드는 각 추천에 `그날 샀더라면 현재 플러스/마이너스 N.N%`(SELL은 대응 문구)를 표시한다. 또한 전체 추천 수, 승률, 평균/중앙 수익률, 가격 미확인 수를 제공한다. 이는 사후 관측이며 새로운 거래 신호가 아니다.

## 검증

- Domain, Parser, Policy, 출처 필터, 구조화 schema, 프롬프트 테스트
- KST schedule, cron 다음 실행 계산, lease, 중복 방지, worker 재시작을 위한 결정적 clock 테스트
- 재시도와 부분 성공을 위한 fake OpenAI/HTTP/Telegram/price adapter 테스트
- 그래프 노드 및 재시도 전환에 대한 FastAPI/SSE 테스트
- migration 및 PostgreSQL repository 테스트
- 관련 PR 병합 후 최근 금요일 4회 × 25건 실제 OpenAI 실행과 보호된 텍스트를 제외한 안전한 분석 보고서
- `uv run pytest`, `uv run python -m compileall app tests`, `git diff --check`, Docker Compose migration smoke test, dashboard health 확인

## 변경 이력

- 2026-08-05: 사용자가 말한 “종목”을 개별 기업이 아닌 투자 테마로 정정했다. 초기 테마는 반도체·AI·대체에너지이며, 수집 필터는 투자 테마와 뉴스 주제를 동시에 만족하는 문서만 통과시킨다.
- 2026-08-05: 최근 금요일 진단 실행에서도 실행·추천 결과를 DB에 보존하고, BUY/SELL 기준일 가격을 조회 가능한 경우 즉시 snapshot으로 저장하도록 범위를 확장했다. 가격 조회 실패는 추천 실행 실패로 만들지 않는다.
- 2026-08-05: 설계·목표·계획 문서는 한국어로 작성한다는 사용자 규칙을 추가했다.

## 범위 제한

- 자동 증권 주문이나 포트폴리오 실행을 하지 않는다.
- 무제한 과거 크롤링이나 provider HTML scraping을 하지 않는다.
- DB에 secret을 저장하지 않는다.
- 비거래일에는 직전 거래 가능 종가를 사용하고 해당 거래일을 명시한다.
