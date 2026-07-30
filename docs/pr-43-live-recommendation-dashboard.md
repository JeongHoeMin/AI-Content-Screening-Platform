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
- 2026-07-30: 실제 DART 공시 제목에서 `단일판매·공급계약`을 event fact로 보존할 수 있도록, 해당 공시 사실만 `financial_event`의 보수적 긍정 영향 규칙으로 추가한다. LLM은 공시에 명시된 계약만 관측하고, 영향 방향과 추천은 기존 deterministic catalog·policy가 계속 결정한다.
- 2026-07-30: 실제 실행에서 DART 공시 메타데이터가 일반 뉴스처럼 과도하게 보수 처리되어 event가 비어 있었다. DART source의 제목·요약은 공식 filing metadata임을 extraction prompt에 명시하고, 명시적 `단일판매·공급계약체결` 제목만 major_supply_contract로 관측하도록 범위를 제한한다.
- 2026-07-30: 프롬프트 보완 후에도 provider가 준 DART 공식 메타데이터를 OpenAI가 빈 event로 반환했다. DART 공급계약 제목은 deterministic extractor가 LLM inference에 보충한다. 일반 기사·그 외 공시에는 적용하지 않으며, 이후 screening·cross validation·resolve·impact·recommendation은 기존 LLM/Policy workflow를 그대로 거친다.
- 2026-07-30: 보충 event가 screening 단계에 도달하면서 OpenAI가 `BadRequestError`를 반환했다. 원인은 transport DTO의 `reasons: List[object]`가 OpenAI structured output에서 type 없는 JSON schema(`items: {}`)로 생성되는 것이므로, Parser가 허용하던 malformed primitive 범위는 유지하면서 명시적 primitive union schema로 바꾼다.
- 2026-07-31: 실제 페이지의 빈 뉴스·추천 영역을 재현했다. 브라우저 요청이 기본 limit 50으로 소스별 50건(총 100건)을 처리해 완료 전 빈 화면이 지속됐다. 대시보드 기본 실행은 소스별 3건으로 제한하고, 실행 중 중복 요청을 막으며 실패·빈 결과를 명시적으로 표시한다. 수집/LLM/Policy 책임은 변경하지 않는다.
- 2026-07-31: 소량 실행은 screen 단계까지 진행했지만 cross-validation response DTO의 claims/reasons가 `List[object]`라서 OpenAI structured-output schema가 거부됐다. Parser의 malformed primitive 관측은 유지하며, 세 목록을 typed primitive union으로 전환한다.
- 2026-07-31: 모든 수집 뉴스의 분석 결과를 실시간으로 보여 달라는 요청에 따라, 수집 직후에는 전체 뉴스 목록을 표시하고 extract·screen·cross-validation node 완료 시 해당 기사 카드에 안전한 요약, event, 점수·결정, 검증 상태를 누적한다. SSE에는 원문·prompt·secret·raw provider 응답을 보내지 않는다.
