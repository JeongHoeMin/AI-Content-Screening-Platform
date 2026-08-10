"use client";

import { useState } from "react";

import { AnalysisCards } from "@/components/AnalysisCards";
import { DiagnosticsTable } from "@/components/DiagnosticsTable";
import { ProgressPanel } from "@/components/ProgressPanel";
import {
  PerformanceSummaryPanel,
  RecommendationsTable,
} from "@/components/RecommendationsTable";
import { RunControls } from "@/components/RunControls";
import { SiteNav } from "@/components/SiteNav";
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
    <main>
      <h1>오늘의 투자 인사이트</h1>
      <p>공식 RSS 전문을 수집하고 LangGraph 분석을 거쳐 Policy 기반 후보를 생성합니다.</p>
      <SiteNav current="/" />

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

      <section className="panel">
        <h2>실시간 작업 기록</h2>
        <ol className="timeline">
          {timeline.map((message, index) => (
            <li key={`${index}-${message}`}>{message}</li>
          ))}
        </ol>
      </section>

      <AnalysisCards analyses={analyses} />

      <DiagnosticsTable
        diagnostics={result?.statistics.impact_diagnostics ?? null}
        hasResult={result !== null}
      />

      <section className="panel">
        <h2>선택된 뉴스</h2>
        <div className="cards">
          {!result ? (
            <p className="empty">
              {isRunning
                ? "뉴스를 수집하고 있습니다."
                : (loadError ?? "추천 실행 후 선택된 뉴스를 표시합니다.")}
            </p>
          ) : result.news_cards.length === 0 ? (
            <p className="empty">선택된 뉴스가 없습니다.</p>
          ) : (
            result.news_cards.map((news, index) => (
              <article key={`${index}-${news.url}`} className="card">
                <small>{news.source}</small>
                <h3>{news.title}</h3>
                <p>{news.excerpt}</p>
                <a href={safeHref(news.url)} target="_blank" rel="noreferrer">
                  원문 보기
                </a>
              </article>
            ))
          )}
        </div>
      </section>

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
    </main>
  );
}
