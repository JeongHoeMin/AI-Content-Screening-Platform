# AI Content Screening Platform

## 웹 대시보드 실행

Docker 실행 환경에 아래 환경변수를 설정한다.

```text
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
DART_API_KEY=...
OPENAI_API_KEY=...
```

`.env` 파일에 위 환경변수를 넣은 다음 Docker 서버에서 실행합니다.

```bash
docker compose up --build -d
```

`http://<server>:8000`에서 **오늘의 뉴스를 기준으로 추천받기**를 누르면 Naver 뉴스·OpenDART 공시 수집, KRX CSV 종목 snapshot, LangGraph 노드 진행 상태, 뉴스 카드, Policy 기반 매수·판매 추천을 확인할 수 있습니다.

기본 CSV 경로는 `./data_0551_20260730.csv`입니다. 다른 KRX master 파일을 사용할 때만 다음처럼 host 경로를 지정합니다.

```bash
COMPANY_DIRECTORY_HOST_CSV_PATH=/data/krx-master.csv docker-compose up --build -d
```

CLI 실행도 유지됩니다.

```bash
screening --collect --mode openai --category "반도체" --period-hours 24 --limit 50
```

`--collect`는 `naver_news,dart`를 기본 source로 사용한다. `--sources naver_news` 또는 `--sources dart`로 제한할 수 있다. CLI에서 KRX master CSV를 쓸 때는 `COMPANY_DIRECTORY_MODE=krx_master_csv`와 `COMPANY_DIRECTORY_CSV_PATH`를 함께 설정한다.
