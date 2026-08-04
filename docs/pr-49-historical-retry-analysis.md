# PR-49 — 과거 실행 재현과 수집 실패 분석

## 목표

KST 기준일을 고정한 과거 실행을 재현하고, 실행 결과는 원문·프롬프트 없이 안전한 요약만 PostgreSQL과 JSONL 감사 로그에 남긴다. 수집 실패가 LLM 호출 전에 발생했는지도 구분한다.

## 구현 내용

- `--as-of-kst YYYY-MM-DD`는 해당 날짜 다음 자정(KST)을 배타적 종료 시각으로 바꿔 UTC로 Provider에 전달한다.
- DART·IR RSS·Naver의 기간 필터는 주입된 동일 종료 시각을 사용한다.
- `workflow_execution_audits` 테이블은 실행 ID, 실행 모드, 종료 상태, UTC 시작/종료 시각, 처리 수, 안전한 통계, 오류 유형만 저장한다.
- OpenDART 전문 응답이 ZIP이 아닐 때는 원문을 저장·로그하지 않고, XML의 `status` 숫자만 안전한 오류 코드로 분류한다.
- 전문이 없는 DART 항목은 fallback 요약을 LLM에 보내지 않고, `dart_document_*` recoverable normalize 오류로 분리한다.

## 실제 실행 관측

| KST 기준일 | source | 요청 한도 | 수집 결과 | 분석 입력 | LLM 호출 | 안전한 실패 코드 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 2026-07-31 | DART | 25 | 25건 목록 수신 | 0건 | 0회 | 문서 ZIP 미확보 |
| 2026-07-31 | DART | 1 | 0건 정상화 | 0건 | 0회 | `dart_document_opendart_status_014` |

`014`는 OpenDART 공식 개발 가이드에서 “파일이 존재하지 않습니다”로 정의한 응답이다. 이 오류는 timeout·connection 같은 일시적 transport 오류가 아니므로 LangGraph 재시도 대상이 아니다.

## RSS 전환 판단

현재 환경의 `IR_RSS_FEEDS`는 빈 배열이어서 RSS Provider는 등록된 피드가 없다. DART는 공시 자체의 투자 근거 가치는 유지하지만, 현 전문 API의 `014` 비율이 높아 현재 분석 기본 입력으로 사용하지 않는다.

운영 기본 입력은 등록·검증된 기업 IR RSS로 전환한다. RSS 피드의 HTTP timeout·connection 오류만 재시도 대상으로 두고, 피드의 빈 항목·본문 부족·DART `014`는 즉시 부분 실패로 기록한다. RSS 일반 피드는 과거 항목 보존을 보장하지 않으므로 2026-07-10·17·24의 재현 실행은 당시 수집 스냅샷 또는 장기 보존 피드가 등록된 뒤에만 유효하게 수행할 수 있다.

## 범위 제한

- DART 전문 파일 `014`를 retry로 우회하거나 기사 본문 fallback을 분석하지 않는다.
- RSS URL을 임의로 등록하지 않는다. 운영자가 승인한 기업·기관 공식 피드만 `IR_RSS_FEEDS`에 등록한다.
- 가격 기록·추천 성과 평가는 다음 `recommendation-performance` 작업에서 시세 어댑터와 함께 구현한다.

## 변경 이력

- 2026-08-05: KST historical boundary와 PostgreSQL 실행 감사 저장을 추가했다.
- 2026-08-05: 실제 DART 실행에서 `014`를 확인하고, 전문 실패를 안전한 recoverable 오류 코드로 분리했다.
- 2026-08-05: RSS 기본 전환 원칙과 과거 재현의 보존 한계를 기록했다.
