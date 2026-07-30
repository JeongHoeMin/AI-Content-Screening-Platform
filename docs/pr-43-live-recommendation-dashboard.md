# PR-43 — Live Recommendation Dashboard

## 목표

오늘의 실제 시장 데이터를 대상으로 사용자가 웹 페이지에서 추천 실행을 시작하고, LangGraph 단계 진행 상황·선택 뉴스 카드·최종 매수/관망/주의 종목을 한 화면에서 확인하게 한다.

## 구현 범위

1. FastAPI application: 실행 생성, Server-Sent Events 진행 스트림, 정적 dashboard 제공.
2. 실행 orchestration: 실제 source 수집 후 `Post → Article` 변환, KRX snapshot과 ScreeningWorkflow를 조립하고 LangGraph node update를 safe event로 투영한다.
3. UI: 오늘 날짜, 추천받기 버튼, node timeline, 선택 뉴스 carousel, recommendation table을 제공한다.
4. Docker: 컨테이너에서 UI/API를 실행하는 Dockerfile과 compose environment 계약을 제공한다.
5. 검증: fake collection/workflow로 SSE·result API를 통합 테스트하고, Docker build와 실제 credentials가 있는 환경의 smoke command를 문서화한다.

## 보안·책임 경계

- SSE에는 node name, count, safe status만 내보내며 기사 본문·prompt·secret·raw API response는 보내지 않는다.
- LLM은 기존처럼 관측만 만들며, UI는 Policy가 생성한 recommendation을 표시만 한다.
- 실행 상태와 in-memory run record 갱신은 web harness가 소유한다. Provider/Skill은 web state를 알지 않는다.
- 결과는 현재 process의 bounded in-memory session에만 두며 durable audit는 기존 Harness의 선택적 sink를 사용한다.

## 변경 이력

- 2026-07-30: 사용자 요청으로 실제 추천 UI와 LangGraph 진행 관측을 위한 구현 계획을 작성했다.
- 2026-07-30: LangGraph node completion을 Harness audit와 함께 streaming하고, FastAPI/SSE dashboard 및 Docker 실행 정의를 추가했다.
- 2026-07-30: 실제 Compose 버튼 실행에서 Naver/DART 100건 수집과 KRX snapshot 준비까지 확인했다. KRX external failure는 고정된 safe transport detail만 추가 관측하도록 보완 중이다.
- 2026-07-30: KRX API가 HTTP 401을 반환해 사용자가 제공한 CP949 KRX master CSV를 runtime directory로 사용하는 fallback을 추가한다. 원본 CSV는 수정하지 않고 표준코드·단축코드·종목약명·시장구분만 canonical snapshot으로 변환한다.
- 2026-07-30: Docker Compose는 user-provided KRX master CSV를 read-only mount하는 기본 경로로 전환한다. CSV를 통해 API authorization 없이 reproducible company snapshot을 사용한다.
