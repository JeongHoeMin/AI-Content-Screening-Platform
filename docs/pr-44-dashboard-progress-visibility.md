# PR-44 — Dashboard Progress Visibility and Stage Guide

## 목표

대시보드 실행 중 오래 걸리는 외부 수집·LLM 단계에서도 사용자가 실행이 살아 있는지, 전체 단계 중 어디까지 왔는지, 이후 어떤 작업이 남았는지 판단할 수 있게 한다. 각 단계가 수행하는 작업과 판단 기준도 화면에서 확인할 수 있게 한다.

## 구현 범위

1. 서버: 실행 상태의 현재 단계를 보존하고, 실행 중 주기적인 안전한 heartbeat SSE를 발행한다. 완료 이벤트에는 전체 단계 수와 현재 완료 수를 함께 제공한다.
2. UI: 수집, 종목 스냅샷, 10개 workflow 노드의 전체 진행표를 완료·진행 중·대기 상태로 표시하고, 진행률·경과 시간·남은 단계 수를 갱신한다.
3. UI: 단계별 상세 설명을 접이식으로 제공한다. LLM이 관측하는 점수와 deterministic Policy가 내리는 결정의 책임을 명확히 구분하며, prompt·기사 원문·secret은 표시하지 않는다.
4. 검증: public SSE 모델 및 대시보드 정적 화면 계약을 테스트한다.
5. 런타임: KRX Company Directory를 마운트 CSV가 아닌 KRX OpenAPI에서만 조립한다.

## 범위 제한

- 시간 예측이나 완료 시각을 보장하지 않는다. 외부 제공자와 LLM 응답 시간은 변동 가능하므로, 실제 경과 시간과 잔여 단계만 표시한다.
- 진행 UI는 workflow·policy의 의사결정, LLM prompt, 수집/분석 결과를 변경하지 않는다.
- heartbeat에는 현재 안전한 단계 식별자와 경과 시간만 보내며 원문, prompt, credential, raw provider response는 포함하지 않는다.
- KRX OpenAPI key는 기존 `.env`의 `KRX_API_KEY`로만 주입하며 Compose volume이나 CSV fallback을 사용하지 않는다.

## 변경 이력

- 2026-07-31: 장시간 단계가 멈춘 것처럼 보이지 않도록 진행 가시성과 단계별 처리 기준 설명을 추가하는 계획을 작성했다.
- 2026-07-31: 수집·종목 스냅샷·10개 workflow node를 12단계 진행표로 투영하고, 실행 중에는 5초 간격의 안전한 SSE heartbeat로 연결과 현재 단계 처리를 확인하게 했다. 시간 완료 예측은 제공하지 않고 실제 경과 시간과 남은 단계 수만 표시한다.
- 2026-07-31: 각 진행 항목에 작업 및 기준을 접이식으로 표시했다. 특히 AI Screening은 LLM의 점수 관측과 deterministic Policy의 40/70 임계값 결정을 구분해 설명한다.
- 2026-07-31: CSV를 사용하지 말라는 요구에 맞춰 dashboard Compose runtime을 `krx_api` 모드로 전환한다. KRX master CSV volume과 host path 환경 계약은 제거하고, API key 누락·API 오류는 안전한 configuration/transport failure로 계속 처리한다.
- 2026-07-31: KRX API는 당일 종목 목록을 아직 제공하지 않을 수 있어, API 응답이 모두 빈 경우에만 이전 7일을 최신순으로 재조회한다. CSV fallback은 추가하지 않으며, 최초로 유효한 API snapshot의 날짜를 directory version으로 보존한다.
- 2026-07-31: 대시보드 실행 버튼 옆에 전체 분석 대상 수 선택(적게 10, 중간 25, 많이 50, 최대 100)을 추가한다. Provider의 source별 수집 limit과 혼동하지 않도록, 서버는 선택 수를 두 source에 나눠 요청한 뒤 수집 결과를 선택 수만큼만 분석 대상으로 제한한다.
- 2026-07-31: 50건 실행에서 ACCEPT 6건이었지만 recommendation은 0건이었다. LLM/Screening 결론을 임의로 완화하지 않고, impact observation·event fact 부재·기업 resolution·impact exclusion·score company 수를 안전한 통계와 화면에 노출해 실제 병목을 확인한다. 확인된 병목에 한해 Domain/Policy 계약을 유지하는 좁은 보완을 적용한다.
- 2026-07-31: 실제 재실행에서 승인 이벤트는 모두 KOSPI 반등 같은 macro event로, 직접 기업과 catalog fact가 없어 종목 추천으로 전환하지 않는 것이 타당했다. 반면 50개 입력의 20개 단위 structured extraction은 일부 batch만 성공했다. 응답 완결성과 부분 성공을 높이기 위해 extraction batch를 10기사로 제한한다. 이는 EventFact/Impact/Recommendation Policy를 완화하지 않으며, 최대 100건에서도 extraction 10 + screening 최대 5 + cross-validation 최대 5 요청으로 기존 실행 예산 20 이내다.
- 2026-07-31: 오늘 DART 결과에는 명시적 단일판매·공급계약체결 공시가 존재한다. 이 공식 공시는 기존 deterministic augmenter의 좁은 대상이지만, augmenter가 LLM 성공 inference만 순회해 실패 batch의 공시를 잃고 있었다. 실패 batch라도 이 정확한 공시 패턴만 deterministic inference로 보존하고, 이후 Screening·Policy·Cross Validation·Recommendation은 기존 경로로 계속 처리한다.
- 2026-07-31: 50건 실제 OpenAI 검증에서 추출 batch 5개가 모두 성공했고, 7개 이벤트 중 직접 근거 1개가 점수화됐다. 공식 공급계약 공시를 근거로 `SNT에너지(100840)`가 BUY, 1.0점으로 표출됐다. 나머지 6개는 impact observation이 없는 macro/factless event로 보존되며 종목 추천으로 확장하지 않았다.
