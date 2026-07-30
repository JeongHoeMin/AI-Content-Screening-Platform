# PR-42 — Real Market Data Providers v1

## 목표

Naver 뉴스 검색과 OpenDART 공시 목록을 실제 `Provider → RawPost → Normalizer → Post → Article` 흐름에 연결하고, KRX OpenAPI 기반 canonical company directory를 추가한다. 실 API credentials는 environment에서만 읽고 로그·result에 기록하지 않는다.

## 승인된 환경변수

- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
- `DART_API_KEY`
- `KRX_API_KEY`

## 구현 범위

1. Naver 뉴스 search provider: 공식 `/v1/search/news.json` API, HTTP auth headers, query/start/display/sort transport validation, HTML title/description text normalization.
2. OpenDART disclosure provider: 공식 `/api/list.json`, date range/market filter transport validation, disclosure metadata를 raw post로 보존한다. 원문 다운로드는 후속 단위다.
3. provider config와 bootstrap registry: source마다 독립 config와 timeout, recoverable provider error를 사용한다.
4. KRX directory: `AUTH_KEY` header와 `basDd` JSON body를 사용해 사용자가 제공한 종목 마스터 API를 호출한다. KOSPI(`stk_isu_base_info`), KOSDAQ(`ksq_isu_base_info`), KONEX(`knx_isu_base_info`)의 `OutBlock_1`을 immutable canonical company directory로 변환한다.
5. collected `Post`를 `Article`로 변환해 기존 ScreeningWorkflow에 전달하는 application Harness/CLI는 provider contracts가 검증된 뒤 별도 단위로 추가한다.

## 확인된 KRX API 계약

- KOSPI: `https://data-dbg.krx.co.kr/svc/apis/sto/stk_isu_base_info`
- KOSDAQ: `https://data-dbg.krx.co.kr/svc/apis/sto/ksq_isu_base_info`
- KONEX: `https://data-dbg.krx.co.kr/svc/apis/sto/knx_isu_base_info`
- 공통 요청: `AUTH_KEY` header와 `{"basDd": "YYYYMMDD"}` JSON body
- 공통 응답: `OutBlock_1` 배열의 `ISU_CD`, `ISU_SRT_CD`, `ISU_NM`, `ISU_ABBRV`, `ISU_ENG_NM`, `LIST_DD`, `MKT_TP_NM` 등을 사용한다.

## 보안·실패 원칙

- client secret, DART/ KRX key, raw HTTP body, 기사 원문은 로그에 남기지 않는다.
- provider 하나의 timeout/HTTP/transport 오류는 sibling source를 막지 않고 `SkillResult.errors`에 제한된 error code로 보존한다.
- API 호출은 injected HTTP transport로 분리해 network-free tests로 검증한다.

## 비범위

- 뉴스 전문 scraping, KRX API service 신청/결제, 자동매매, external scheduler deployment, API key provisioning은 이번 단위에 포함하지 않는다.

## 변경 이력

- 2026-07-30: 사용자 제공 environment-variable 계약 및 공식 API 문서를 기준으로 최초 계획 작성.
- 2026-07-30: 사용자가 KOSPI·KOSDAQ·KONEX 종목기본정보 명세를 제공했다. CSV는 입력 검증용으로만 보존하고 runtime canonical directory는 KRX API를 사용하도록 범위를 확정했다.
