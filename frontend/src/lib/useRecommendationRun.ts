"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { STAGES, WORKFLOW_ONLY_STAGES } from "./stages";
import {
  EMPTY_SUMMARY,
  type AnalysisItem,
  type DashboardEvent,
  type DashboardRunResult,
  type PerformanceItem,
  type PerformanceResponse,
  type StageCounts,
} from "./types";

export type RunStatus = "idle" | "running" | "completed" | "failed";

export interface RunProgress {
  active: string | null;
  status: RunStatus;
  startedAt: number | null;
  lastHeartbeat: number | null;
  failureStage: string | null;
  failureAttempts: number | null;
  errorType: string | null;
  completedStages: Set<string>;
  skippedStages: Set<string>;
  stageCounts: Record<string, StageCounts>;
}

export interface RunRequest {
  limit: number;
  themes: string[];
  topics: string[];
}

const INITIAL_PROGRESS: RunProgress = {
  active: null,
  status: "idle",
  startedAt: null,
  lastHeartbeat: null,
  failureStage: null,
  failureAttempts: null,
  errorType: null,
  completedStages: new Set(),
  skippedStages: new Set(),
  stageCounts: {},
};

const STREAMED_EVENTS = [
  "collecting",
  "collected",
  "directory",
  "workflow_started",
  "workflow",
  "heartbeat",
  "completed",
  "failed",
] as const;

/**
 * Fold one server event into progress, mirroring the stage bookkeeping the
 * original dashboard did: collection events complete their own stage, and a
 * workflow node completing implies every earlier workflow stage was skipped.
 */
function applyEvent(previous: RunProgress, event: DashboardEvent): RunProgress {
  const completedStages = new Set(previous.completedStages);
  const skippedStages = new Set(previous.skippedStages);
  const stageCounts = event.stage_counts
    ? { ...previous.stageCounts, ...event.stage_counts }
    : previous.stageCounts;

  if (event.type === "collected") completedStages.add("collect");
  if (event.type === "workflow_started") completedStages.add("directory");
  if (event.type === "workflow" && event.node && WORKFLOW_ONLY_STAGES.has(event.node)) {
    const nodeIndex = STAGES.findIndex((stage) => stage.key === event.node);
    for (const stage of STAGES.slice(2, nodeIndex)) {
      if (!completedStages.has(stage.key)) skippedStages.add(stage.key);
    }
    skippedStages.delete(event.node);
    completedStages.add(event.node);
  }

  return {
    ...previous,
    completedStages,
    skippedStages,
    stageCounts,
    active: event.active_stage,
    lastHeartbeat: Date.now(),
    ...(event.type === "failed"
      ? {
          failureStage: event.failure_stage ?? event.active_stage,
          failureAttempts: event.failure_attempts ?? null,
          errorType: event.error_type ?? null,
        }
      : {}),
  };
}

export interface RunState {
  progress: RunProgress;
  timeline: string[];
  analyses: AnalysisItem[];
  result: DashboardRunResult | null;
  performanceByIdentity: Map<string, PerformanceItem>;
  performanceSummary: PerformanceResponse["summary"];
  loadError: string | null;
  elapsedMs: number;
  start: (request: RunRequest) => Promise<void>;
}

export function useRecommendationRun(): RunState {
  const [progress, setProgress] = useState<RunProgress>(INITIAL_PROGRESS);
  const [timeline, setTimeline] = useState<string[]>([]);
  const [analyses, setAnalyses] = useState<AnalysisItem[]>([]);
  const [result, setResult] = useState<DashboardRunResult | null>(null);
  const [performance, setPerformance] = useState<PerformanceResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const analysesById = useRef(new Map<string, AnalysisItem>());
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => sourceRef.current?.close();
  }, []);

  useEffect(() => {
    if (progress.status !== "running" || progress.startedAt === null) return;
    const startedAt = progress.startedAt;
    // start() resets the counter to 0, so the first tick a second from now is
    // the earliest value that would actually differ from what is displayed.
    const timer = window.setInterval(
      () => setElapsedMs(Date.now() - startedAt),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [progress.status, progress.startedAt]);

  const mergeAnalyses = useCallback((items: AnalysisItem[]) => {
    if (items.length === 0) return;
    for (const item of items) analysesById.current.set(item.id, item);
    setAnalyses([...analysesById.current.values()]);
  }, []);

  const loadResult = useCallback(async (runId: string) => {
    const response = await fetch(`/api/runs/${runId}`);
    if (!response.ok) throw new Error("result_load_failed");
    const data: DashboardRunResult = await response.json();
    setResult(data);
    if (data.stage_counts) {
      const counts = data.stage_counts;
      setProgress((previous) => ({
        ...previous,
        stageCounts: { ...previous.stageCounts, ...counts },
      }));
    }
    analysesById.current.clear();
    for (const item of data.analyses) analysesById.current.set(item.id, item);
    setAnalyses([...analysesById.current.values()]);

    const performanceResponse = await fetch(
      `/api/recommendations/performance?run_id=${encodeURIComponent(data.run_id)}`,
    );
    setPerformance(
      performanceResponse.ok
        ? await performanceResponse.json()
        : { items: [], summary: EMPTY_SUMMARY, evaluated_at: "" },
    );
  }, []);

  const start = useCallback(
    async (request: RunRequest) => {
      sourceRef.current?.close();
      analysesById.current.clear();
      setTimeline([]);
      setAnalyses([]);
      setResult(null);
      setPerformance(null);
      setLoadError(null);
      setElapsedMs(0);
      setProgress({
        ...INITIAL_PROGRESS,
        active: "collect",
        status: "running",
        startedAt: Date.now(),
        lastHeartbeat: Date.now(),
        completedStages: new Set(),
        skippedStages: new Set(),
        stageCounts: {},
      });

      let runId: string;
      try {
        const response = await fetch("/api/runs", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(request),
        });
        if (!response.ok) throw new Error("run_start_failed");
        ({ run_id: runId } = await response.json());
      } catch {
        setLoadError("추천 실행을 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.");
        setProgress((previous) => ({ ...previous, status: "failed", active: null }));
        return;
      }

      let terminal = false;
      const source = new EventSource(`/api/runs/${runId}/events`);
      sourceRef.current = source;

      for (const name of STREAMED_EVENTS) {
        source.addEventListener(name, (event) => {
          const data: DashboardEvent = JSON.parse((event as MessageEvent).data);
          setProgress((previous) => applyEvent(previous, data));
          if (data.type !== "heartbeat" && data.message) {
            setTimeline((previous) => [...previous, data.message]);
          }
          mergeAnalyses(data.analyses ?? []);

          if (data.type === "completed") {
            terminal = true;
            source.close();
            setProgress((previous) => ({
              ...previous,
              active: null,
              status: "completed",
            }));
            loadResult(runId).catch(() =>
              setLoadError("결과를 불러오지 못했습니다. 다시 실행해 주세요."),
            );
          }

          if (data.type === "failed") {
            terminal = true;
            source.close();
            const detail = `중단 단계: ${data.failure_stage ?? data.active_stage ?? "-"} · 오류: ${data.error_type ?? "-"} · 시도: ${data.failure_attempts ?? 1}/3`;
            setLoadError(`뉴스 분석이 완료되지 않았습니다. ${detail}`);
            setProgress((previous) => ({ ...previous, status: "failed" }));
          }
        });
      }

      source.onerror = () => {
        if (terminal) return;
        source.close();
        setLoadError("실시간 연결이 끊겼습니다. 다시 실행해 주세요.");
        setProgress((previous) => ({ ...previous, status: "failed", active: null }));
      };
    },
    [loadResult, mergeAnalyses],
  );

  const performanceByIdentity = new Map(
    (performance?.items ?? []).map((item) => [
      `${item.run_id}:${item.recommendation_index}`,
      item,
    ]),
  );

  return {
    progress,
    timeline,
    analyses,
    result,
    performanceByIdentity,
    performanceSummary: performance?.summary ?? EMPTY_SUMMARY,
    loadError,
    elapsedMs,
    start,
  };
}
