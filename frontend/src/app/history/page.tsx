"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { Badge, Button, Card, EmptyState, TableScroll, Td, Th } from "@/components/ui";
import { formatKst, formatPercent, priceErrorLabel, returnTone } from "@/lib/format";
import { entryRetryFeedback, replaceHistoryItem, replaceHistoryRun } from "@/lib/history";
import type {
  PerformanceItem,
  PerformanceSummary,
  RunHistoryResponse,
} from "@/lib/types";

type LoadState = "loading" | "loaded" | "failed";

function identity(item: PerformanceItem): string {
  return `${item.run_id}-${item.recommendation_index}`;
}

function summaryLine(summary: PerformanceSummary): string {
  const winRate = summary.positive_win_rate === null ? "-" : `${summary.positive_win_rate.toFixed(1)}%`;
  const mean = summary.mean_return_percent === null ? "-" : `${summary.mean_return_percent.toFixed(1)}%`;
  return `확인 ${summary.confirmed_count}건 · 미확인 ${summary.unavailable_count}건 · BUY ${summary.buy_count}건 · SELL ${summary.sell_count}건 · 승률 ${winRate} · 평균 ${mean}`;
}

function ReturnCell({ item }: { item: PerformanceItem }) {
  if (item.entry_price === null) return <span className="text-ink-muted">진입가 확인 필요</span>;
  if (item.return_percent === null) {
    return <span className="text-ink-muted">현재가 미확인 · {priceErrorLabel(item.latest_error_kind)}</span>;
  }
  return <span className={returnTone(item.return_percent) === "positive" ? "font-semibold text-positive" : returnTone(item.return_percent) === "negative" ? "font-semibold text-negative" : "font-semibold text-ink"}>{formatPercent(item.return_percent)}</span>;
}

export default function HistoryPage() {
  const [state, setState] = useState<LoadState>("loading");
  const [history, setHistory] = useState<RunHistoryResponse | null>(null);
  const [refreshingRuns, setRefreshingRuns] = useState<Set<string>>(new Set());
  const [backfillingItems, setBackfillingItems] = useState<Set<string>>(new Set());
  const [retriedItems, setRetriedItems] = useState<Set<string>>(new Set());

  const refreshRun = useCallback(async (runId: string) => {
    setRefreshingRuns((current) => new Set(current).add(runId));
    try {
      const response = await fetch(`/api/runs/history/${encodeURIComponent(runId)}/refresh`, { method: "POST" });
      if (!response.ok) throw new Error("run_refresh_failed");
      const refreshedRun = await response.json();
      setHistory((current) => (current ? replaceHistoryRun(current, refreshedRun) : current));
    } catch {
      // Stored data remains visible; this run can be retried without reloading all history.
    } finally {
      setRefreshingRuns((current) => {
        const next = new Set(current);
        next.delete(runId);
        return next;
      });
    }
  }, []);

  const backfillEntry = useCallback(async (item: PerformanceItem) => {
    const itemIdentity = identity(item);
    setBackfillingItems((current) => new Set(current).add(itemIdentity));
    try {
      const response = await fetch(
        `/api/runs/history/${encodeURIComponent(item.run_id)}/items/${item.recommendation_index}/entry-price`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("entry_backfill_failed");
      const refreshedItem = await response.json();
      setHistory((current) => (current ? replaceHistoryItem(current, refreshedItem) : current));
      setRetriedItems((current) => {
        const next = new Set(current);
        if (refreshedItem.entry_price === null) next.add(itemIdentity);
        else next.delete(itemIdentity);
        return next;
      });
    } catch {
      // Keep the original error reason visible when the historical close remains unavailable.
    } finally {
      setBackfillingItems((current) => {
        const next = new Set(current);
        next.delete(itemIdentity);
        return next;
      });
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void fetch("/api/runs/history")
      .then((response) => {
        if (!response.ok) throw new Error("history_load_failed");
        return response.json();
      })
      .then((data: RunHistoryResponse) => {
        if (cancelled) return;
        setHistory(data);
        setState("loaded");
        data.runs.forEach((run) => void refreshRun(run.run_id));
      })
      .catch(() => {
        if (!cancelled) setState("failed");
      });
    return () => {
      cancelled = true;
    };
  }, [refreshRun]);

  return (
    <AppShell
      current="/history"
      title="추천 이력"
      description="저장된 추천 기록은 먼저 표시하고, 손익률은 회차별 현재가 확인이 끝나는 순서대로 갱신합니다."
    >
      {state === "loading" && <Card><EmptyState>추천 이력을 불러오고 있습니다.</EmptyState></Card>}
      {state === "failed" && <Card><EmptyState>이력을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.</EmptyState></Card>}
      {state === "loaded" && history?.runs.length === 0 && <Card><EmptyState>아직 가격이 기록된 추천 이력이 없습니다.</EmptyState></Card>}

      {state === "loaded" && history?.runs.map((run) => (
        <Card
          key={run.run_id}
          title={formatKst(run.observed_at)}
          description={summaryLine(run.summary)}
          actions={<Button variant="secondary" size="sm" onClick={() => void refreshRun(run.run_id)} disabled={refreshingRuns.has(run.run_id)}>{refreshingRuns.has(run.run_id) ? "갱신 중…" : "현재가 갱신"}</Button>}
        >
          {run.items.length === 0 ? <EmptyState>이 회차에는 매수·매도 추천이 없습니다.</EmptyState> : (
            <TableScroll>
              <thead><tr><Th>종목</Th><Th>코드</Th><Th>추천</Th><Th align="right">진입가</Th><Th align="right">현재가</Th><Th align="right">손익률</Th></tr></thead>
              <tbody>
                {run.items.map((item) => {
                  const itemIdentity = identity(item);
                  const backfilling = backfillingItems.has(itemIdentity);
                  const retryFeedback = entryRetryFeedback(item, retriedItems.has(itemIdentity));
                  return <tr key={itemIdentity}>
                    <Td className="font-medium">{item.company_name}</Td>
                    <Td className="font-mono text-xs text-ink-muted">{item.ticker}</Td>
                    <Td><Badge tone={item.action === "buy" ? "positive" : "negative"}>{item.action.toUpperCase()}</Badge></Td>
                    <Td align="right">
                      {item.entry_price === null ? <div className="flex items-center justify-end gap-2"><span className="text-ink-muted">{retryFeedback ? `${retryFeedback}: ` : ""}{priceErrorLabel(item.entry_error_kind)}</span><Button size="sm" variant="ghost" title="추천 시각 기준 KRX 종가 재조회" onClick={() => void backfillEntry(item)} disabled={backfilling}>{backfilling ? "조회 중…" : "재조회"}</Button></div> : `${item.entry_price.toLocaleString()}원`}
                    </Td>
                    <Td align="right">{item.latest_price === null ? "-" : `${item.latest_price.toLocaleString()}원`}</Td>
                    <Td align="right"><ReturnCell item={item} /></Td>
                  </tr>;
                })}
              </tbody>
            </TableScroll>
          )}
        </Card>
      ))}
    </AppShell>
  );
}
