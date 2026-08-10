"use client";

import { describePricePerformance, formatKst } from "@/lib/format";
import type { PerformanceItem, PerformanceSummary, RecommendationRow } from "@/lib/types";

interface RecommendationsTableProps {
  runId: string | null;
  recommendations: RecommendationRow[];
  performanceByIdentity: Map<string, PerformanceItem>;
  emptyMessage: string;
}

function actionTone(action: string): string {
  if (action.includes("buy")) return "buy";
  if (action.includes("sell")) return "sell";
  return "";
}

export function PerformanceSummaryPanel({
  summary,
  hasResult,
}: {
  summary: PerformanceSummary;
  hasResult: boolean;
}) {
  return (
    <section className="panel">
      <h2>추천 성과 요약</h2>
      {!hasResult ? (
        <p className="empty">추천 실행 후 가격 성과를 표시합니다.</p>
      ) : (
        <>
          <p>
            {`확인 ${summary.confirmed_count}건 · 미확인 ${summary.unavailable_count}건 · BUY ${summary.buy_count}건 · SELL ${summary.sell_count}건`}
          </p>
          <p>
            {`승률 ${summary.positive_win_rate === null ? "-" : `${summary.positive_win_rate.toFixed(1)}%`} · 평균 ${summary.mean_return_percent === null ? "-" : `${summary.mean_return_percent.toFixed(1)}%`} · 중앙값 ${summary.median_return_percent === null ? "-" : `${summary.median_return_percent.toFixed(1)}%`}`}
          </p>
          <p>최신 평가: {formatKst(summary.latest_observed_at)}</p>
        </>
      )}
    </section>
  );
}

export function RecommendationsTable({
  runId,
  recommendations,
  performanceByIdentity,
  emptyMessage,
}: RecommendationsTableProps) {
  return (
    <section className="panel">
      <h2>매수 · 판매 추천</h2>
      <table>
        <thead>
          <tr>
            <th>종목</th>
            <th>코드</th>
            <th>점수</th>
            <th>추천</th>
            <th>근거</th>
            <th>가격 성과</th>
          </tr>
        </thead>
        <tbody>
          {recommendations.length === 0 ? (
            <tr>
              <td colSpan={6} className="empty">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            recommendations.map((item) => {
              const performance = performanceByIdentity.get(
                `${runId}:${item.recommendation_index}`,
              );
              const { basis, detail } = describePricePerformance(performance);
              return (
                <tr key={`${item.recommendation_index}-${item.company_name}`}>
                  <td>{item.company_name}</td>
                  <td>{item.ticker ?? "-"}</td>
                  <td>{item.score}</td>
                  <td className={actionTone(item.action)}>{item.action}</td>
                  <td>{item.reason_code}</td>
                  <td>
                    {basis && (
                      <>
                        {basis}
                        <br />
                      </>
                    )}
                    {detail}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </section>
  );
}
