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
import { Badge, Card, type Tone } from "@/components/ui";

interface ProgressPanelProps {
  progress: RunProgress;
  elapsedMs: number;
}

const STATE_CHIP: Record<StageState, string> = {
  waiting: "border-line bg-surface-sunken text-ink-subtle",
  active: "border-accent bg-accent/15 text-ink ring-1 ring-accent",
  done: "border-positive/40 bg-positive/10 text-positive",
  skipped: "border-line bg-surface-sunken text-ink-subtle line-through",
  failed: "border-negative bg-negative/15 text-negative",
};

const STATUS_TONE: Record<RunProgress["status"], Tone> = {
  idle: "neutral",
  running: "accent",
  completed: "positive",
  failed: "negative",
};

const STATUS_LABEL: Record<RunProgress["status"], string> = {
  idle: "실행 전",
  running: "실행 중",
  completed: "완료",
  failed: "중단됨",
};

function stageState(progress: RunProgress, key: string): StageState {
  if (progress.failureStage === key) return "failed";
  if (progress.completedStages.has(key)) return "done";
  if (progress.skippedStages.has(key)) return "skipped";
  if (key === progress.active && progress.status === "running") return "active";
  return "waiting";
}

function connectionText(progress: RunProgress): string {
  if (!progress.lastHeartbeat) return "실행을 시작하면 서버 상태를 확인합니다.";
  const time = new Date(progress.lastHeartbeat).toLocaleTimeString("ko-KR");
  return `서버 확인 ${time}`;
}

function RetryPath({ progress }: { progress: RunProgress }) {
  const retryStage = progress.failureStage ?? progress.active ?? "";
  const isRetryable = RETRYABLE_STAGES.has(retryStage);
  const failed = isRetryable && progress.failureAttempts !== null;

  const detail = failed
    ? `${retryStage} 단계가 ${progress.errorType ?? "안전한 오류 분류"}로 ${progress.failureAttempts}/3회 시도 후 중단되었습니다.`
    : isRetryable
      ? `${retryStage} 단계는 일시적 연결·인증 오류에 최초 실행 뒤 5초·10초 간격으로 최대 3회 시도합니다.`
      : DEFAULT_RETRY_DETAIL;

  return (
    <div
      className={`mt-4 rounded-xl border-l-4 bg-surface-sunken px-4 py-3 text-sm ${
        failed
          ? "border-l-negative"
          : isRetryable
            ? "border-l-warning"
            : "border-l-line-strong"
      }`}
    >
      <p className="font-semibold text-ink">LLM 재시도 경로</p>
      <p className="mt-1 leading-relaxed text-ink-muted">{detail}</p>
    </div>
  );
}

export function ProgressPanel({ progress, elapsedMs }: ProgressPanelProps) {
  const completed = progress.completedStages.size;
  const skipped = progress.skippedStages.size;
  const finished = completed + skipped;
  const percent = Math.round((finished / STAGES.length) * 100);

  return (
    <Card
      title="진행 상황"
      actions={<Badge tone={STATUS_TONE[progress.status]}>{STATUS_LABEL[progress.status]}</Badge>}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 text-sm">
        <span className="font-semibold text-ink tabular-nums">
          {completed}/{STAGES.length} 단계 완료
          {skipped > 0 && ` · ${skipped}단계 미실행`}
        </span>
        <span className="text-ink-muted tabular-nums">
          경과 {formatElapsed(elapsedMs)} · {connectionText(progress)}
        </span>
      </div>

      <div
        className="mt-3 h-2 overflow-hidden rounded-full bg-surface-sunken"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent to-positive transition-[width] duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>

      <ol className="mt-4 flex flex-wrap gap-2">
        {STAGES.map((stage, index) => {
          const state = stageState(progress, stage.key);
          const counts = progress.stageCounts[stage.key];
          return (
            <li key={stage.key}>
              <details className="group">
                <summary
                  className={`flex cursor-pointer list-none items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${STATE_CHIP[state]}`}
                >
                  <span className="tabular-nums opacity-70">{index + 1}</span>
                  <span>{stage.name}</span>
                  <span className="opacity-70">{STAGE_STATE_LABELS[state]}</span>
                </summary>
                <div className="mt-2 max-w-md rounded-xl border border-line bg-surface-sunken px-3 py-2.5 text-xs leading-relaxed text-ink-muted">
                  <p>
                    <span className="font-semibold text-ink">작업</span> {stage.work}
                  </p>
                  <p className="mt-1">
                    <span className="font-semibold text-ink">기준</span> {stage.criteria}
                  </p>
                  {counts && (
                    <p className="mt-1 tabular-nums">
                      <span className="font-semibold text-ink">건수</span> 입력{" "}
                      {counts.input_count} · 통과 {counts.accepted_count} · 탈락{" "}
                      {counts.rejected_count}
                    </p>
                  )}
                </div>
              </details>
            </li>
          );
        })}
      </ol>

      <RetryPath progress={progress} />
    </Card>
  );
}
