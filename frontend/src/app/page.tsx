"use client";

import { useState } from "react";

import { AnalysisCards } from "@/components/AnalysisCards";
import { AppShell } from "@/components/AppShell";
import { DiagnosticsTable } from "@/components/DiagnosticsTable";
import { ProgressPanel } from "@/components/ProgressPanel";
import {
  PerformanceSummaryPanel,
  RecommendationsTable,
} from "@/components/RecommendationsTable";
import { RunControls } from "@/components/RunControls";
import { Card, EmptyState } from "@/components/ui";
import { safeHref } from "@/lib/format";
import { useRecommendationRun } from "@/lib/useRecommendationRun";

export default function DashboardPage() {
  const [limit, setLimit] = useState(10);
  const [themes, setThemes] = useState<string[]>([]);
  const [topics, setTopics] = useState<string[]>([]);

  const {
    progress,
    timeline,
    analyses,
    result,
    performanceByIdentity,
    performanceSummary,
    loadError,
    elapsedMs,
    start,
  } = useRecommendationRun();

  const isRunning = progress.status === "running";

  const recommendationsEmptyMessage = isRunning
    ? "추천 분석을 진행하고 있습니다."
    : loadError
      ? loadError
      : result
        ? "현재 정책 기준을 통과한 추천 종목이 없습니다."
        : "추천 실행 후 결과를 표시합니다.";

  return (
    <AppShell
      current="/"
      title="오늘의 투자 인사이트"
      description="공식 RSS를 수집하고 LangGraph 분석을 거쳐 Policy 기반 후보를 생성합니다. 실행 결과는 Telegram 자격 증명이 설정된 경우에도 안전한 요약으로 발송됩니다."
    >

      <RunControls
        limit={limit}
        themes={themes}
        topics={topics}
        disabled={isRunning}
        isRunning={isRunning}
        onLimitChange={setLimit}
        onThemesChange={setThemes}
        onTopicsChange={setTopics}
        onRun={() => void start({ limit, themes, topics })}
      />

      <ProgressPanel progress={progress} elapsedMs={elapsedMs} />

      <Card title="실시간 작업 기록" description="서버가 전달하는 안전한 진행 상태만 표시합니다.">
        {timeline.length === 0 ? <EmptyState>추천 실행을 시작하면 진행 기록이 여기에 표시됩니다.</EmptyState> : <ol className="space-y-2 text-sm text-ink-muted">
          {timeline.map((message, index) => (
            <li key={`${index}-${message}`} className="rounded-lg border border-line bg-surface-sunken px-3 py-2">{message}</li>
          ))}
        </ol>}
      </Card>

      <AnalysisCards analyses={analyses} />

      <DiagnosticsTable
        diagnostics={result?.statistics.impact_diagnostics ?? null}
        hasResult={result !== null}
      />

      <Card title="선택된 뉴스" description="추천 판단에 사용된 기사 목록입니다.">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {!result ? (
            <EmptyState>
              {isRunning
                ? "뉴스를 수집하고 있습니다."
                : (loadError ?? "추천 실행 후 선택된 뉴스를 표시합니다.")}
            </EmptyState>
          ) : result.news_cards.length === 0 ? (
            <EmptyState>선택된 뉴스가 없습니다.</EmptyState>
          ) : (
            result.news_cards.map((news, index) => (
              <article key={`${index}-${news.url}`} className="rounded-xl border border-line bg-surface-sunken p-4">
                <small className="text-xs font-medium text-ink-subtle">{news.source}</small>
                <h3 className="mt-1 font-semibold text-ink">{news.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink-muted">{news.excerpt}</p>
                <a className="mt-3 inline-flex text-sm font-medium text-accent-strong hover:text-ink" href={safeHref(news.url)} target="_blank" rel="noreferrer">
                  원문 보기
                </a>
              </article>
            ))
          )}
        </div>
      </Card>

      <PerformanceSummaryPanel
        summary={performanceSummary}
        hasResult={result !== null}
      />

      <RecommendationsTable
        runId={result?.run_id ?? null}
        recommendations={result?.recommendations ?? []}
        performanceByIdentity={performanceByIdentity}
        emptyMessage={recommendationsEmptyMessage}
      />
    </AppShell>
  );
}
