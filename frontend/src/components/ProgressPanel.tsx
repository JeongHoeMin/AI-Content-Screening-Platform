"use client";

import {
  DEFAULT_RETRY_DETAIL,
  RETRYABLE_STAGES,
  STAGES,
  STAGE_STATE_LABELS,
  type StageState,
} from "@/lib/stages";
import { formatElapsed } from "@/lib/format";
import type { RunProgress } from "@/lib/useRecommendationRun";

interface ProgressPanelProps {
  progress: RunProgress;
  elapsedMs: number;
}

function graphStageState(progress: RunProgress, key: string): StageState {
  if (progress.failureStage === key) return "failed";
  if (progress.completedStages.has(key)) return "done";
  if (progress.skippedStages.has(key)) return "skipped";
  if (key === progress.active && progress.status === "running") return "active";
  return "waiting";
}

function listStageState(progress: RunProgress, key: string): StageState {
  if (progress.completedStages.has(key)) return "done";
  if (progress.skippedStages.has(key)) return "skipped";
  if (key === progress.active && progress.status === "running") return "active";
  return "waiting";
}

function summaryText(progress: RunProgress): string {
  const completed = progress.completedStages.size;
  const skipped = progress.skippedStages.size;
  const remaining = Math.max(STAGES.length - completed - skipped, 0);
  switch (progress.status) {
    case "running":
      return `${completed}/${STAGES.length} 단계 완료 · ${skipped}단계 미실행 · ${remaining}단계 남음`;
    case "completed":
      return `${completed}/${STAGES.length} 단계 완료 · ${skipped}단계 미실행`;
    case "failed":
      return `실행 실패 · ${completed}/${STAGES.length} 단계 완료`;
    default:
      return "실행 전";
  }
}

function connectionText(progress: RunProgress): string {
  if (!progress.lastHeartbeat) return "실행을 시작하면 상태를 확인합니다.";
  const time = new Date(progress.lastHeartbeat).toLocaleTimeString("ko-KR");
  const phase = progress.active
    ? "현재 단계 처리 중"
    : progress.status === "failed"
      ? "중단됨"
      : "완료";
  return `서버 확인 ${time} · ${phase}`;
}

function RetryPath({ progress }: { progress: RunProgress }) {
  const retryStage = progress.failureStage ?? progress.active ?? "";
  const isRetryable = RETRYABLE_STAGES.has(retryStage);

  if (isRetryable && progress.failureAttempts) {
    return (
      <div className="retry-path failed">
        <strong>LLM 재시도 경로</strong>
        <span>
          {` ${retryStage} 단계가 ${progress.errorType ?? "안전한 오류 분류"}로 ${progress.failureAttempts}/3회 시도 후 중단되었습니다.`}
        </span>
      </div>
    );
  }

  return (
    <div className={isRetryable ? "retry-path active" : "retry-path"}>
      <strong>LLM 재시도 경로</strong>
      <span>
        {isRetryable
          ? ` ${retryStage} 단계는 일시적 연결·인증 오류에 최초 실행 뒤 5초·10초 간격으로 최대 3회 시도합니다.`
          : ` ${DEFAULT_RETRY_DETAIL}`}
      </span>
    </div>
  );
}

export function ProgressPanel({ progress, elapsedMs }: ProgressPanelProps) {
  const finished = progress.completedStages.size + progress.skippedStages.size;
  const percent = (finished / STAGES.length) * 100;

  return (
    <section className="panel">
      <h2>전체 진행 상황</h2>
      <div className="progress-meta">
        <span>{summaryText(progress)}</span>
        <span>경과 시간 {formatElapsed(elapsedMs)}</span>
        <span>{connectionText(progress)}</span>
      </div>

      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>

      <div className="workflow-graph" aria-label="실제 워크플로우 그래프">
        {STAGES.map((stage, index) => {
          const counts = progress.stageCounts[stage.key];
          return (
            <div
              key={stage.key}
              className={`graph-node ${graphStageState(progress, stage.key)}`}
            >
              <span className="graph-index">{index + 1}단계</span>
              <span className="graph-name">{stage.name}</span>
              {counts && (
                <span className="graph-counts">
                  {`입력 ${counts.input_count} · 통과 ${counts.accepted_count} · 탈락 ${counts.rejected_count}`}
                </span>
              )}
            </div>
          );
        })}
      </div>

      <RetryPath progress={progress} />

      <ol className="stage-list">
        {STAGES.map((stage) => {
          const state = listStageState(progress, stage.key);
          return (
            <li key={stage.key}>
              <details className={`stage ${state}`} open={state === "active"}>
                <summary>
                  <span className="stage-state">{STAGE_STATE_LABELS[state]}</span>
                  <span className="stage-name">{stage.name}</span>
                </summary>
                <div className="stage-guide">
                  <p>
                    <strong>작업:</strong> {stage.work}
                  </p>
                  <p>
                    <strong>기준:</strong> {stage.criteria}
                  </p>
                </div>
              </details>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
