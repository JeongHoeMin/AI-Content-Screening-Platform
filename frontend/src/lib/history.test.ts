import { describe, expect, it } from "vitest";

import { replaceHistoryItem, replaceHistoryRun } from "./history";
import type { RunHistoryItem, RunHistoryResponse } from "./types";

const summary = {
  confirmed_count: 0,
  unavailable_count: 1,
  buy_count: 1,
  sell_count: 0,
  positive_win_rate: null,
  mean_return_percent: null,
  median_return_percent: null,
  latest_observed_at: null,
};

function run(runId: string, latestPrice: number | null): RunHistoryItem {
  return {
    run_id: runId,
    observed_at: "2026-08-10T06:00:00Z",
    summary,
    items: [
      {
        run_id: runId,
        recommendation_index: 0,
        company_name: "삼성전자",
        ticker: "005930",
        action: "buy",
        entry_price: 72000,
        entry_provider: "krx",
        entry_basis: "close",
        entry_observed_at: "2026-08-10T06:00:00Z",
        entry_error_kind: null,
        latest_price: latestPrice,
        latest_observed_at: latestPrice === null ? null : "2026-08-10T07:00:00Z",
        latest_error_kind: latestPrice === null ? "not_found" : null,
        return_percent: latestPrice === null ? null : 1,
      },
    ],
  };
}

describe("replaceHistoryRun", () => {
  it("replaces only the refreshed run and preserves other visible runs", () => {
    const current: RunHistoryResponse = {
      runs: [run("newer", null), run("older", null)],
      evaluated_at: "2026-08-10T07:00:00Z",
    };

    const updated = replaceHistoryRun(current, run("older", 72700));

    expect(updated.runs.map((candidate) => candidate.run_id)).toEqual([
      "newer",
      "older",
    ]);
    expect(updated.runs[0].items[0].latest_price).toBeNull();
    expect(updated.runs[1].items[0].latest_price).toBe(72700);
  });
});

describe("replaceHistoryItem", () => {
  it("updates only the recovered entry while retaining the run and its other rows", () => {
    const current: RunHistoryResponse = {
      runs: [run("run-1", null)],
      evaluated_at: "2026-08-10T07:00:00Z",
    };
    const recovered = { ...current.runs[0].items[0], entry_price: 72000 };

    const updated = replaceHistoryItem(current, recovered);

    expect(updated.runs).toHaveLength(1);
    expect(updated.runs[0].items).toHaveLength(1);
    expect(updated.runs[0].items[0].entry_price).toBe(72000);
  });
});
