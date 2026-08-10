"use client";

import { describePricePerformance, formatKst } from "@/lib/format";
import type { PerformanceItem, PerformanceSummary, RecommendationRow } from "@/lib/types";
import { Badge, Card, EmptyState, TableScroll, Td, Th } from "@/components/ui";

interface RecommendationsTableProps {
  runId: string | null;
  recommendations: RecommendationRow[];
  performanceByIdentity: Map<string, PerformanceItem>;
  emptyMessage: string;
}

export function PerformanceSummaryPanel({
  summary,
  hasResult,
}: {
  summary: PerformanceSummary;
  hasResult: boolean;
}) {
  return (
    <Card title="추천 성과 요약" description="추천 시점의 가격과 최신 가격을 단순 비교한 참고 정보입니다.">
      {!hasResult ? (
        <EmptyState>추천 실행 후 가격 성과를 표시합니다.</EmptyState>
      ) : (
        <div className="space-y-1 text-sm text-ink-muted">
          <p>
            {`확인 ${summary.confirmed_count}건 · 미확인 ${summary.unavailable_count}건 · BUY ${summary.buy_count}건 · SELL ${summary.sell_count}건`}
          </p>
          <p>
            {`승률 ${summary.positive_win_rate === null ? "-" : `${summary.positive_win_rate.toFixed(1)}%`} · 평균 ${summary.mean_return_percent === null ? "-" : `${summary.mean_return_percent.toFixed(1)}%`} · 중앙값 ${summary.median_return_percent === null ? "-" : `${summary.median_return_percent.toFixed(1)}%`}`}
          </p>
          <p>최신 평가: {formatKst(summary.latest_observed_at)}</p>
        </div>
      )}
    </Card>
  );
}

export function RecommendationsTable({
  runId,
  recommendations,
  performanceByIdentity,
  emptyMessage,
}: RecommendationsTableProps) {
  return (
    <Card title="매수 · 판매 추천" description="Policy가 선택한 후보와 가격 성과를 함께 확인합니다.">
      <TableScroll>
        <thead>
          <tr>
            <Th>종목</Th><Th>코드</Th><Th align="right">점수</Th><Th>추천</Th><Th>근거</Th><Th>가격 성과</Th>
          </tr>
        </thead>
        <tbody>
          {recommendations.length === 0 ? (
            <tr>
              <Td colSpan={6}><EmptyState>{emptyMessage}</EmptyState></Td>
            </tr>
          ) : (
            recommendations.map((item) => {
              const performance = performanceByIdentity.get(
                `${runId}:${item.recommendation_index}`,
              );
              const { basis, detail } = describePricePerformance(performance);
              return (
                <tr key={`${item.recommendation_index}-${item.company_name}`}>
                  <Td className="font-medium">{item.company_name}</Td>
                  <Td className="font-mono text-xs text-ink-muted">{item.ticker ?? "-"}</Td>
                  <Td align="right">{item.score}</Td>
                  <Td><Badge tone={item.action.includes("buy") ? "positive" : item.action.includes("sell") ? "negative" : "neutral"}>{item.action}</Badge></Td>
                  <Td className="text-ink-muted">{item.reason_code}</Td>
                  <Td className="text-ink-muted">
                    {basis && (
                      <>
                        {basis}
                        <br />
                      </>
                    )}
                    {detail}
                  </Td>
                </tr>
              );
            })
          )}
        </tbody>
      </TableScroll>
    </Card>
  );
}
