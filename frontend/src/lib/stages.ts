export interface StageDefinition {
  key: string;
  name: string;
  work: string;
  criteria: string;
}

export const STAGES: StageDefinition[] = [
  {
    key: "collect",
    name: "뉴스·공시 수집",
    work: "공식 RSS 원문을 수집해 공통 Article로 정규화합니다.",
    criteria: "출처 실패는 다른 출처의 수집 결과를 보존합니다.",
  },
  {
    key: "directory",
    name: "종목 기준정보 준비",
    work: "KRX 상장사 스냅샷을 준비합니다.",
    criteria: "LLM이 임의 종목을 만들지 않습니다.",
  },
  {
    key: "evaluate",
    name: "분석 대상 점검",
    work: "기사 최소 구조를 점검합니다.",
    criteria: "입력 품질만 확인하며 투자 판단은 하지 않습니다.",
  },
  {
    key: "extract",
    name: "이벤트 추출",
    work: "기사에서 구조화 이벤트와 근거를 추출합니다.",
    criteria: "Parser가 형식·문단 근거를 검증합니다.",
  },
  {
    key: "deduplicate",
    name: "이벤트 중복 판정",
    work: "동일 사건 후보를 보수적으로 비교해 대표 이벤트만 남깁니다.",
    criteria: "same·confidence 80 이상만 병합합니다.",
  },
  {
    key: "screen",
    name: "AI Screening",
    work: "관련성·중요도·신뢰도를 관측합니다.",
    criteria:
      "관련성 또는 중요도 40점 미만은 REJECT, 교차검증 필요 시 REVIEW, 세 점수 모두 70점 이상은 ACCEPT입니다.",
  },
  {
    key: "cross_validate",
    name: "교차 검증",
    work: "REVIEW 이벤트의 지지·충돌 관계를 관측합니다.",
    criteria: "Policy가 독립 출처와 검증 상태를 계산합니다.",
  },
  {
    key: "resolve",
    name: "이벤트·기업 연결",
    work: "이벤트를 KRX 기업 기준에 연결합니다.",
    criteria: "미해결 기업은 종목 근거에서 제외합니다.",
  },
  {
    key: "analyze",
    name: "영향 분석",
    work: "확정 이벤트의 영향을 분석합니다.",
    criteria: "이 단계는 매매 결론을 만들지 않습니다.",
  },
  {
    key: "aggregate",
    name: "근거 집계",
    work: "기업별 유효 근거를 모읍니다.",
    criteria: "원본 이벤트 연결을 보존합니다.",
  },
  {
    key: "score",
    name: "종목 점수 계산",
    work: "결정적 전략으로 점수를 계산합니다.",
    criteria: "LLM의 매매 지시가 아닙니다.",
  },
  {
    key: "recommend",
    name: "추천 결정",
    work: "점수와 정책 임계값을 적용합니다.",
    criteria: "Recommendation Policy가 결론을 만듭니다.",
  },
  {
    key: "select_candidates",
    name: "후보 선택",
    work: "표시할 후보를 선택합니다.",
    criteria: "점수·추천 자체는 수정하지 않습니다.",
  },
];

export const RETRYABLE_STAGES = new Set([
  "extract",
  "deduplicate",
  "screen",
  "cross_validate",
]);

/** Stages driven by the workflow node stream rather than collection events. */
export const WORKFLOW_ONLY_STAGES = new Set(
  STAGES.slice(2).map((stage) => stage.key),
);

export const DEFAULT_RETRY_DETAIL =
  "추출·중복 판정·스크리닝·교차검증 단계만 일시적 연결·인증 오류에 최초 실행 뒤 5초·10초 간격으로 최대 3회 시도합니다.";

export type StageState = "waiting" | "active" | "done" | "skipped" | "failed";

export const STAGE_STATE_LABELS: Record<StageState, string> = {
  waiting: "대기",
  active: "진행 중",
  done: "완료",
  skipped: "미실행",
  failed: "실패",
};
