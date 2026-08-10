# PR-48 AI Screening 세부 점수표

LLM은 관련성·중요도·신뢰도 총점 대신 9개 세부 criterion과 영역별 근거를 구조화해 반환한다. Parser는 strict DTO와 item 단위 부분 성공을 유지하고, `ScreeningScorecardPolicy`가 동일 가중치·half-up 반올림으로 세 총점을 계산한다. 대시보드는 기존 총점과 세부 관측값을 함께 표시하며 raw response나 prompt는 표시하지 않는다.
