# AI Content Screening Platform

## 웹 대시보드 실행

Docker 실행 환경에 아래 환경변수를 설정한다.

```text
KRX_API_KEY=...
OPENAI_API_KEY=...
IR_RSS_FEEDS=[{"id":"company-ir","url":"https://ir.example.com/rss.xml","company_name":"회사명"}]
```

환경변수 파일을 준비한 다음 Docker 서버에서 실행합니다. 기본 파일명은 `.env`이며, 다른 보안 경로의 파일은
Compose 표준 `--env-file` 옵션으로 지정합니다.

```bash
docker compose up --build -d

# 예: 별도 보안 경로의 환경 파일
docker compose --env-file /secure/screening.env up --build -d
```

`http://<server>:8000`에서 **오늘의 뉴스를 기준으로 추천받기**를 누르면 운영자가 등록한 기업 IR RSS 전문 수집, KRX OpenAPI 종목 snapshot, LangGraph 노드 진행 상태, 뉴스 카드, Policy 기반 매수·판매 추천을 확인할 수 있습니다. `IR_RSS_FEEDS`에는 승인한 기업·기관의 전문 RSS/Atom URL만 등록합니다. KRX snapshot은 실행마다 `KRX_API_KEY`로 API를 호출해 생성하며 CSV를 마운트하거나 읽지 않습니다.

CLI 실행도 유지됩니다.

```bash
screening --collect --mode openai --period-hours 24 --limit 25
```

`--collect`는 `ir_rss`를 기본 source로 사용한다. DART는 전문 파일이 존재하는 경우에만 보조 진단 source로 명시적으로 선택할 수 있으며, Naver 검색 결과는 분석 입력으로 사용하지 않는다. KRX API를 사용할 때는 `COMPANY_DIRECTORY_MODE=krx_api`와 `KRX_API_KEY`를 설정한다.
