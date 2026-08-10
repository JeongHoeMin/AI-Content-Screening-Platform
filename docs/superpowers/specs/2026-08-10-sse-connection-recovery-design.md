# SSE 연결 복구 및 진단 설계

## 목표

추천 워크플로우가 계속 실행 중이거나 정상 완료됐을 때 브라우저의 일시적인 SSE 연결 종료가
대시보드를 잘못된 `중단됨` 상태로 고정하지 않게 한다. 동시에 다음 실행에서 연결 종료가
browser, Next.js proxy, 또는 dashboard stream 중 어느 경계에서 관측됐는지 안전한 메타데이터로
확인한다.

## 선택한 접근

SSE를 WebSocket으로 교체하지 않는다. WebSocket도 연결 단절과 복구가 필요하므로 이 문제의
해결책이 아니다. 기존 SSE는 진행 이벤트 전달에 계속 사용하고, 실행 ID의 결과 조회를 terminal
상태의 기준으로 추가 사용한다.

EventSource 오류가 나면 프런트는 즉시 `failed`로 확정하거나 source를 닫지 않는다. 제한된 횟수로
SSE를 재연결하는 동안 `GET /api/runs/{run_id}`를 조회한다. 결과가 준비되면 기존 `loadResult` 흐름으로
완료 상태와 결과를 표시한다. 아직 실행 중인 `409`은 정상적인 진행 상태로 취급한다. 서버가 terminal
실패를 반환하면 safe failure 상태만 표시한다. 복구 횟수를 소진하고 결과도 확인할 수 없을 때만
연결 실패 상태를 표시한다.

## 관측 계약

Dashboard backend는 SSE 구독 시작, terminal event 전송, generator 취소 또는 예기치 않은 stream 종료를
structlog event로 남긴다. 각 event에는 `run_id`, 제한된 lifecycle 값, terminal event type 여부만 넣는다.
기사 본문, prompt, raw SDK 응답, cookie, authorization header, IP 주소, 예외 전문은 넣지 않는다.

브라우저는 EventSource 오류, 재연결 시도, 결과 조회로 복구, 복구 소진을 제한된 diagnostic endpoint로
보내거나 서버 로그에 남길 수 있는 최소 인터페이스로 전달한다. 사용자 화면에는 내부 원인을 노출하지
않고 `연결을 복구하는 중` 또는 실제 terminal 결과만 보여 준다. 구현 선택은 기존 API 소비자와 SSE
payload 계약을 바꾸지 않아야 한다.

## 상태 흐름

1. `POST /api/runs`가 실행 ID를 만들고 SSE가 진행 event를 전달한다.
2. SSE 오류가 나면 UI는 `recovering` 상태로 유지하고 진행 시간·마지막 관측은 보존한다.
3. UI는 bounded backoff로 SSE를 다시 구독하고 같은 실행 ID의 결과 endpoint를 조회한다.
4. 결과 endpoint가 성공하면 UI는 `completed`와 결과를 표시한다. `409`이면 아직 실행 중이므로 복구를
   계속한다. 명시적 server failure만 `failed`로 표시한다.
5. 정해진 복구 예산 안에 stream과 terminal 결과를 모두 확보하지 못한 경우에만 UI가 연결 실패를 표시한다.

## 테스트

- Backend SSE 테스트는 구독 시작·terminal 전송·취소/종료의 제한 로그 필드를 확인한다.
- Frontend hook 테스트는 EventSource 오류 뒤 결과 endpoint가 완료를 반환하면 `completed`로 전환하고
  결과를 보이는지 확인한다.
- 아직 실행 중인 `409`과 복구 예산 소진도 별도로 검증한다.
- 정상 completed/failed SSE와 기존 결과 API 계약은 회귀 테스트한다.

## 범위와 제한

이 변경은 transport 단절 원인 자체를 단정하거나 제거하지 않는다. 프록시/브라우저/네트워크에서 다시
발생할 수 있는 연결 단절을 사용자가 잘못된 실패로 보지 않게 하고, 후속 로그로 실제 경계를 좁히는
것이 범위다. 실행 상태는 현재 dashboard process의 메모리에 있으므로 dashboard 컨테이너 재시작 뒤에는
진행 중 실행을 복구하지 않는다.
