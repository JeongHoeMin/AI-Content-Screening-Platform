# AI Content Screening Platform

> 기업 IR 공시를 근거 기반으로 검증해 종목 추천까지 만드는 AI 스크리닝 파이프라인

이 프로젝트는 단순한 뉴스 요약기가 아니라, 운영자가 승인한 기업 IR RSS 전문을 이벤트 단위로 구조화하고, 투자 테마·뉴스 주제로 필터링한 뒤, 교차 검증을 거쳐 매수·관망·주의 종목을 추천하는 시스템입니다. LLM은 판단을 보조하는 관측자일 뿐이고, Accept/Review/Reject, 점수 산정, 최종 추천 같은 결정은 전부 코드로 작성된 Policy가 내립니다.

---

## 핵심 설계 원칙

- **LLM은 결정을 내리지 않는다.** LLM은 이벤트 추출, 중요도 평가, 기사 간 관계(supports/conflicts) 관측만 수행하고, Verified 여부·점수·추천 같은 최종 결정은 Policy가 전담합니다.
- **Prompt와 Business Logic은 분리한다.** "독립 출처 2개 이상이면 Verified" 같은 규칙은 Prompt가 아니라 Policy 코드에 있습니다.
- **모든 LLM 응답은 Parser가 검증한다.** Transport DTO는 최소 구조만 보장하고, 타입·범위·중복·index·enum 검증은 Parser가 수행한 뒤 Domain 객체로 변환합니다.
- **부분 실패를 허용한다.** 이벤트 하나의 실패가 배치 전체 실패로 번지지 않도록, 가능한 한 성공한 sibling 결과를 보존합니다.
- **수집 조건은 결정적 코드가 소유한다.** 투자 테마(반도체·AI·대체에너지 등 종목군)와 뉴스 주제는 versioned catalog의 문자열 규칙으로 판정하며, LLM은 이 필터의 통과·제외를 결정하지 않습니다.
- **Mock mode와 실제 LLM(OpenAI) mode는 동일한 Workflow를 공유한다.** Mock은 LLM 관측만 결정적 구현으로 대체하므로, 빠르고 재현 가능한 계약 검증 경로로 쓰입니다.

더 자세한 원칙과 비목표(Non-goals)는 [PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md)를 참고하세요.

---

## 전체 파이프라인

```text
IR RSS 전문 수집 → 정규화 → 투자 테마·뉴스 주제 Filter → 이벤트 추출 → AI 스크리닝
→ 교차 검증(Cross Validation) → Resolve(Accept/Review/Reject)
→ 기업 매핑(Company Resolution) → 영향 분석(Impact Analysis)
→ 종목 점수화(Scoring) → 후보 선정(Candidate Selection) → 포트폴리오 추천
```

| 단계 | 책임 | 위치 |
| --- | --- | --- |
| Provider | 운영자가 등록한 기업 IR RSS 전문 수집 (가공 없음), DART는 보조 진단 source | [app/providers/](app/providers/) |
| Normalizer | Provider별 데이터를 공통 `Article`로 변환 | [app/models/normalize.py](app/models/normalize.py) |
| Collection Filter | 선택한 투자 테마·뉴스 주제를 versioned catalog로 결정적 판정 | [app/filters/](app/filters/) |
| Extractor | `Article` → `NewsEvent` 구조화 추출 | [app/extractors/](app/extractors/) |
| Screener | 이벤트의 Relevance/Importance/Credibility 평가 (scorecard 포함) | [app/screeners/](app/screeners/) |
| Cross Validator | 다른 기사와 비교해 supports/conflicts/unrelated 판단 | [app/cross_validators/](app/cross_validators/) |
| Deduplicator | 동일 이벤트 판단 및 정규 이벤트 선정 | [app/deduplicators/](app/deduplicators/) |
| Resolver | 위 결과를 종합해 Accept/Review/Reject 결정 | [app/resolvers/](app/resolvers/) |
| Company Resolver | 이벤트를 KRX 상장 종목에 매핑 | [app/resolvers/](app/resolvers/), [app/config/company_directory.py](app/config/company_directory.py) |
| Analyzer | 기업/산업/시장에 미치는 영향 분석 | [app/analyzers/](app/analyzers/) |
| Aggregator | 영향 관측치를 점수 근거(evidence)로 집계 | [app/aggregators/](app/aggregators/) |
| Scorer | 근거 기반 종목 점수 계산 | [app/scorers/](app/scorers/) |
| Recommender | 점수 기반 매수/관망/주의 추천 생성 | [app/recommenders/](app/recommenders/) |
| Candidate Selection | 추천 결과에서 최종 후보 랭킹 산정 | [app/candidates/](app/candidates/) |
| Workflow | LangGraph 기반 전체 단계 연결 | [app/workflows/](app/workflows/) |
| Harness | 실행 감사(audit), 재시도, 알림, 로그/DB 보존 | [app/harness/](app/harness/) |
| Scheduled Worker | PostgreSQL cron 설정을 lease로 claim해 정기 추천 실행 | [app/scheduled_worker.py](app/scheduled_worker.py) |

전체 계층 구조와 의존성 방향은 [ARCHITECTURE.md](docs/ARCHITECTURE.md)에 상세히 설명되어 있습니다.

---

## 기술 스택

- **언어/런타임**: Python (>=3.9), [uv](https://docs.astral.sh/uv/) 패키지 매니저
- **웹 서버**: FastAPI + Uvicorn (SSE 기반 실시간 워크플로우 진행 상태 표시)
- **LLM/오케스트레이션**: OpenAI SDK (Responses API, structured output), LangChain, LangGraph
- **데이터 검증**: Pydantic
- **DB/마이그레이션**: PostgreSQL, asyncpg, Alembic
- **알림**: Telegram Bot API (best-effort 실행 완료 요약 전송)
- **로깅**: structlog (구조화 JSON 로그)
- **CLI**: argparse, Rich
- **테스트**: pytest

---

## 빠른 시작

### 1. 웹 대시보드 + 정기 실행 (Docker, 권장)

`docker compose`는 5개 서비스를 함께 기동합니다: `postgres`, `db-migrate`(Alembic 마이그레이션 후 종료), `dashboard`(FastAPI JSON/SSE API), `frontend`(Next.js 웹 UI), `schedule-worker`(정기 추천 + 텔레그램 알림).

화면은 Next.js(`frontend/`)가 담당하고 `dashboard`는 API만 제공합니다. 브라우저는 `frontend`의 `/api/*` 프록시를 통해 API를 호출하므로 API 포트를 따로 열지 않아도 됩니다.

환경변수 파일을 준비합니다. 기본 파일명은 `.env`이며, 다른 보안 경로의 파일은 Compose 표준 `--env-file` 옵션으로 지정할 수 있습니다.

```text
POSTGRES_PASSWORD=...
OPENAI_API_KEY=...
KRX_API_KEY=...
IR_RSS_FEEDS=[{"id":"company-ir","url":"https://ir.example.com/rss.xml","company_name":"회사명"}]

# 선택: 정기 실행 설정 화면(/settings) 보호
SCHEDULE_SETTINGS_PASSWORD=32자_이상_임의_비밀번호
SCHEDULE_COOKIE_SECURE=true

# 선택: 텔레그램 완료 알림 (둘 다 설정해야 활성화)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

추천 가격의 실시간 조회는 선택 사항이다. 비밀값 대신 아래 **설정 이름만** 보안 환경 파일에 추가한다.
두 KIS 자격 증명은 함께 설정해야 하며, 둘 다 없으면 KRX 종가 fallback만 사용한다.

- `KIS_APP_KEY`, `KIS_APP_SECRET`
- `KIS_ACCOUNT_PRODUCT_CODE` (기본값 `01`)
- `KIS_BASE_URL` (기본값 `https://openapi.koreainvestment.com:9443`)
- `KIS_TIMEOUT_SECONDS` (기본값 `10`)

키·secret·authorization header·외부 응답 원문은 저장소, 문서 예시, 로그에 넣지 않는다.

```bash
docker compose up --build -d

# 예: 별도 보안 경로의 환경 파일 사용
docker compose --env-file /secure/screening.env up --build -d
```

`http://<server>:3000`에서 **"오늘의 뉴스를 기준으로 추천받기"** 를 누르면 다음을 확인할 수 있습니다. 추천 이력은 `/history`, 정기 실행 설정은 `/settings`입니다.

환경 파일의 KIS 설정을 추가하거나 변경했다면 dashboard와 worker를 재생성해 적용한다.

```bash
docker compose --env-file /secure/screening.env up --build -d --force-recreate dashboard schedule-worker
```

`frontend`는 빌드 시점에 API 주소를 굽습니다(Next.js rewrites 제약). compose 기본값은 `http://dashboard:8000`이며, 바꾸려면 `docker-compose.yml`의 `API_BASE_URL` build arg를 수정하고 이미지를 다시 빌드해야 합니다.

- 운영자가 등록한 기업 IR RSS 전문 수집 (`IR_RSS_FEEDS`에는 승인한 기업·기관의 RSS/Atom URL만 등록)
- KRX OpenAPI 종목 snapshot (실행마다 `KRX_API_KEY`로 API를 호출해 생성, CSV 마운트/캐시 없음)
- LangGraph 노드 단위 진행 상태 (SSE 실시간 워크플로우 그래프)
- 뉴스 카드 및 근거(evidence)
- Policy 기반 매수·판매 추천 결과

`/settings`는 `SCHEDULE_SETTINGS_PASSWORD`가 일치할 때만 접근할 수 있고, 성공하면 HttpOnly 세션 쿠키를 발급해 정기 실행(cron) 설정을 관리할 수 있습니다. 실행 로그는 `./runtime/logs`에 구조화 JSONL로 저장되며 Git에는 포함되지 않습니다.

정기 실행과 텔레그램 알림 운영 방법은 [정기 추천 및 텔레그램 운영](docs/정기-추천-및-텔레그램-운영.md)을 참고하세요.

### 2. 로컬 개발 환경 (uv)

```bash
uv sync
uv run pytest
```

### 3. CLI 실행

```bash
screening --collect --mode openai --period-hours 24 --limit 25
```

- `--collect`는 `ir_rss`를 기본 source로 사용합니다.
- DART는 전문 파일이 존재하는 경우에만 보조 진단 source로 명시적으로 선택할 수 있습니다 (`--sources dart`).
- Naver 검색 결과는 더 이상 분석 입력으로 사용하지 않습니다.
- `--mode mock`으로 실행하면 LLM 호출 없이 결정적 mock 구현으로 동일한 Workflow를 검증할 수 있습니다.
- KRX API를 사용하려면 `COMPANY_DIRECTORY_MODE=krx_api`와 `KRX_API_KEY`를 설정합니다.
- 로컬 Article JSON을 직접 스크리닝하려면 `--input <path>`를 사용합니다.
- 저장된 실행 감사 로그를 집계하려면 `--audit-report <path>`를 사용합니다.

전체 옵션은 `screening --help` 또는 [app/cli.py](app/cli.py)를 참고하세요.

---

## 필요한 환경변수

| 변수 | 용도 |
| --- | --- |
| `IR_RSS_FEEDS` | 신뢰할 기업 IR RSS 전문 설정 JSON (`[{"id","url","company_name"}, ...]`) |
| `DART_API_KEY` | OpenDART 보조 진단 수집 (선택) |
| `KRX_API_KEY` | KRX OpenAPI 종목 snapshot 조회 (`COMPANY_DIRECTORY_MODE=krx_api`일 때 필수) |
| `KIS_APP_KEY` / `KIS_APP_SECRET` | 선택적 KIS 실시간 가격 조회 (반드시 함께 설정) |
| `KIS_ACCOUNT_PRODUCT_CODE` / `KIS_BASE_URL` / `KIS_TIMEOUT_SECONDS` | KIS 가격 조회 설정 (각각 기본 `01`, 운영 URL, `10`) |
| `OPENAI_API_KEY` | OpenAI 기반 이벤트 추출/스크리닝/교차검증 (`--mode openai`) |
| `POSTGRES_PASSWORD` 등 | Docker Compose PostgreSQL 접속 정보 |
| `DATABASE_URL` | `postgresql+asyncpg://` 형식의 비동기 접속 문자열 |
| `APP_LOG_PATH` / `WORKFLOW_AUDIT_LOG_PATH` | 구조화 로그 및 실행 감사 로그 경로 |
| `ARTICLE_MIN_BODY_LENGTH` / `ARTICLE_MAX_BODY_LENGTH` | 수집 기사 본문 길이 유효 범위 (기본 300~50000) |
| `SCHEDULE_SETTINGS_PASSWORD` | `/settings` 접근 비밀번호 (32자 이상, 서버가 HttpOnly 세션 쿠키로만 변환) |
| `SCHEDULE_COOKIE_SECURE` | 세션 쿠키 Secure 속성 (기본 `true`, 로컬 HTTP 검증 시에만 `false`) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | 정기 실행 완료 요약 전송 (둘 다 설정해야 활성화, 하나만 설정 시 worker 시작 거부) |

---

## 테스트

```bash
uv run pytest
uv run python -m compileall app tests
```

테스트는 LLM이 특정 문장이나 점수를 정확히 맞히는지가 아니라, transport boundary·Parser·Policy·Workflow·CLI의 **결정적 계약**을 검증합니다. 실제 OpenAI API를 호출하는 smoke test는 API key가 명시적으로 제공된 경우에만 별도로 실행됩니다. 자세한 내용은 [TESTING_GUIDE.md](docs/TESTING_GUIDE.md)를 참고하세요.

---

## 로깅 및 관측성

- 로그는 `structlog`만 사용하며 batch index, event/evidence index, 처리 시간, 제한된 error kind 같은 운영 메타데이터만 기록합니다.
- 기사 원문, Prompt, LLM SDK 전체 응답, API key, 텔레그램 토큰/채팅 ID, 개인정보는 로그·JSONL audit 어디에도 기록하지 않습니다.
- Docker 실행 시 `./runtime/logs`에 애플리케이션 로그와 워크플로우 실행 감사(execution audit) 로그가 JSONL로 보존됩니다.
- `ScreeningExecutionHarness`가 모든 실행의 terminal audit를 생성해 JSONL과 PostgreSQL에 함께 저장하고, 설정된 provider request 상한을 넘지 않도록 예산을 관리하며, 실패 시 best-effort 운영 알림을 보냅니다.
- 정기 실행은 `schedule-worker`가 PostgreSQL lease와 `(job_id, scheduled_for)` 고유 제약으로 같은 실행 슬롯을 중복 처리하지 않도록 보장하며, 완료 후에만 텔레그램 요약을 best-effort로 전송합니다(전송 실패가 분석 결과에 영향을 주지 않음).

---

## 프로젝트 문서

| 문서 | 내용 |
| --- | --- |
| [docs/PROJECT_GUIDE.md](docs/PROJECT_GUIDE.md) | 프로젝트 목표, 핵심 원칙, Layer 규칙, 장기 로드맵 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 계층 구조, 의존성 방향, LLM 경계, 실패 처리 원칙 |
| [docs/DEVELOPMENT_GUIDE.md](docs/DEVELOPMENT_GUIDE.md) | 구현 세부 규칙 및 코딩 컨벤션 |
| [docs/DOMAIN_MODEL.md](docs/DOMAIN_MODEL.md) | Domain 모델(Article, NewsEvent 등) 설계 |
| [docs/LLM_GUIDELINES.md](docs/LLM_GUIDELINES.md) | LLM 사용 범위와 경계 |
| [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) | 테스트 계층 및 검증 규칙 |
| [docs/WORKFLOW.md](docs/WORKFLOW.md) | LangGraph Workflow 상세 |
| [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | 주요 설계 결정 기록 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 향후 계획 |
| [.agent/docs/task-schema.md](.agent/docs/task-schema.md) | `task.yaml` 필드 정의 및 작성 규칙 |
| [docs/정기-추천-및-텔레그램-운영.md](docs/정기-추천-및-텔레그램-운영.md) | 정기 실행/텔레그램 알림 운영 가이드 |
| [docs/](docs/) | PR 단위 구현 기록 (PR-01 ~ 최신) |
| [AGENTS.md](AGENTS.md) | Claude Code·Codex 공용 작업 절차(task.yaml 기반) |

---

## 프로젝트 상태

완료된 영역: Provider(IR RSS 중심) · Normalizer · Collection Filter(투자 테마/뉴스 주제) · Event Extraction · AI Screening(scorecard 포함) · Cross Validation · Resolve · Company Resolver · Impact Analyzer · Stock Scoring · Recommendation · Candidate Selection · 실행 감사/재시도 분석 · PostgreSQL 기반 정기 스케줄러 · 텔레그램 알림 · Next.js 웹 UI(SSE 워크플로우 그래프, 추천 이력·손익률).

추천 시점과 사후 조회 가격은 화면에서 KST로 표시한다. KIS 실시간 가격을 우선 사용하고 조회할 수 없으면 KRX의 최근 거래일 종가를 사용한다. 둘 다 확인할 수 없으면 `가격 미확인`으로 표시하며 수익률을 추정하지 않는다. 표시는 수수료·세금·배당을 반영하지 않는 사후 단순 가격 비교이며 투자 조언이나 실제 체결 성과가 아니다.

현재 목표는 아니지만 명시적으로 배제하는 항목: 실시간 초단위 자동매매, 가격 예측 모델, 기술적 분석 기반 투자 전략, LLM이 직접 투자 결정을 내리는 시스템, 단일 기사만으로 종목을 추천하는 시스템.
