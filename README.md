# AI Content Screening Platform

## 실제 데이터 수집 실행

Docker 실행 환경에 아래 환경변수를 설정한다.

```text
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...
DART_API_KEY=...
KRX_API_KEY=...
COMPANY_DIRECTORY_MODE=krx_api
OPENAI_API_KEY=...
```

그 다음 아래 명령으로 Naver 뉴스와 OpenDART 공시를 수집해 LLM 관측과 결정적 Policy 기반 종목 추천을 실행한다.

```bash
screening --collect --mode openai --category "반도체" --period-hours 24 --limit 50
```

`--collect`는 `naver_news,dart`를 기본 source로 사용한다. `--sources naver_news` 또는 `--sources dart`로 제한할 수 있다. KRX API snapshot 날짜를 고정해 재현하려면 `KRX_DIRECTORY_DATE=YYYY-MM-DD`를 설정한다.
