"use client";

import { useEffect, useState } from "react";

import { SiteNav } from "@/components/SiteNav";
import { formatKst, formatPercent, priceErrorLabel, returnTone } from "@/lib/format";
import type { PerformanceItem, PerformanceSummary, RunHistoryResponse } from "@/lib/types";

type LoadState = "loading" | "loaded" | "failed";

function ReturnCell({ item }: { item: PerformanceItem }) {
  if (item.entry_price === null) {
    return <>{`가격 미확인 (사유: ${priceErrorLabel(item.entry_error_kind)})`}</>;
  }
  if (item.return_percent === null) {
    return <>{`현재가 미확인 (사유: ${priceErrorLabel(item.latest_error_kind)})`}</>;
  }
  return (
    <span className={returnTone(item.return_percent)}>
      {formatPercent(item.return_percent)}
    </span>
  );
}

function summaryLine(summary: PerformanceSummary): string {
  const winRate =
    summary.positive_win_rate === null
      ? "-"
      : `${summary.positive_win_rate.toFixed(1)}%`;
  const mean =
    summary.mean_return_percent === null
      ? "-"
      : `${summary.mean_return_percent.toFixed(1)}%`;
  return `확인 ${summary.confirmed_count}건 · 미확인 ${summary.unavailable_count}건 · BUY ${summary.buy_count}건 · SELL ${summary.sell_count}건 · 승률 ${winRate} · 평균 ${mean}`;
}

export default function HistoryPage() {
  const [state, setState] = useState<LoadState>("loading");
  const [history, setHistory] = useState<RunHistoryResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/runs/history")
      .then((response) => {
        if (!response.ok) throw new Error("history_load_failed");
        return response.json();
      })
      .then((data: RunHistoryResponse) => {
        if (cancelled) return;
        setHistory(data);
        setState("loaded");
      })
      .catch(() => {
        if (!cancelled) setState("failed");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main>
      <h1>추천 이력</h1>
      <p>과거 추천 실행(run)별로 매수·매도 종목의 진입가 대비 현재가 손익률을 확인합니다.</p>
      <SiteNav current="/history" />

      {state === "loading" && (
        <section className="panel">
          <p className="empty">
            이력을 불러오는 중입니다. 종목별 현재가를 갱신하느라 시간이 걸릴 수 있습니다.
          </p>
        </section>
      )}

      {state === "failed" && (
        <section className="panel">
          <p className="empty">이력을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</p>
        </section>
      )}

      {state === "loaded" && history!.runs.length === 0 && (
        <section className="panel">
          <p className="empty">아직 가격이 기록된 추천 이력이 없습니다.</p>
        </section>
      )}

      {state === "loaded" &&
        history!.runs.map((run) => (
          <article key={run.run_id} className="panel">
            <div className="run-header">
              <span className="run-time">{formatKst(run.observed_at)}</span>
              <span className="run-summary">{summaryLine(run.summary)}</span>
            </div>
            {run.items.length === 0 ? (
              <p className="empty">이 회차에는 매수·매도 추천이 없습니다.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>종목</th>
                    <th>코드</th>
                    <th>추천</th>
                    <th>진입가</th>
                    <th>현재가</th>
                    <th>손익률</th>
                  </tr>
                </thead>
                <tbody>
                  {run.items.map((item) => (
                    <tr key={`${run.run_id}-${item.recommendation_index}`}>
                      <td>{item.company_name}</td>
                      <td>{item.ticker}</td>
                      <td className={item.action === "buy" ? "buy" : "sell"}>
                        {item.action}
                      </td>
                      <td>
                        {item.entry_price === null ? "-" : `${item.entry_price}원`}
                      </td>
                      <td>
                        {item.latest_price === null ? "-" : `${item.latest_price}원`}
                      </td>
                      <td>
                        <ReturnCell item={item} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </article>
        ))}
    </main>
  );
}
