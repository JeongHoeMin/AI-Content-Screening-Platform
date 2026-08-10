import { describe, expect, it } from "vitest";

import {
  describePricePerformance,
  formatElapsed,
  formatKst,
  formatPercent,
  priceErrorLabel,
  returnTone,
  safeHref,
} from "./format";
import type { PerformanceItem } from "./types";

function item(overrides: Partial<PerformanceItem> = {}): PerformanceItem {
  return {
    run_id: "run-1",
    recommendation_index: 0,
    company_name: "삼성전자",
    ticker: "005930",
    action: "buy",
    entry_price: 100,
    entry_provider: "kis",
    entry_basis: "realtime",
    entry_observed_at: "2026-08-05T15:00:00Z",
    entry_error_kind: null,
    latest_price: 110,
    latest_observed_at: "2026-08-06T01:00:00Z",
    latest_error_kind: null,
    return_percent: 10,
    ...overrides,
  };
}

describe("formatKst", () => {
  it("projects a UTC instant onto Asia/Seoul regardless of the host timezone", () => {
    expect(formatKst("2026-08-05T15:00:00Z")).toBe("2026-08-06 00:00 KST");
  });

  it("keeps the KST calendar date when the UTC date is a day behind", () => {
    expect(formatKst("2026-08-05T23:30:00Z")).toBe("2026-08-06 08:30 KST");
  });

  it("reports missing timestamps instead of rendering an invalid date", () => {
    expect(formatKst(null)).toBe("KST 시각 미확인");
  });
});

describe("safeHref", () => {
  it("passes through http and https article links", () => {
    expect(safeHref("https://example.com/a")).toBe("https://example.com/a");
    expect(safeHref("http://example.com/a")).toBe("http://example.com/a");
  });

  it("refuses non-http schemes and unparseable values", () => {
    expect(safeHref("javascript:alert(1)")).toBe("#");
    expect(safeHref("not a url")).toBe("#");
  });
});

describe("formatPercent and returnTone", () => {
  it("signs positive returns and marks direction", () => {
    expect(formatPercent(10)).toBe("+10.0%");
    expect(formatPercent(-2.35)).toBe("-2.4%");
    expect(formatPercent(null)).toBe("-");
    expect(returnTone(1)).toBe("positive");
    expect(returnTone(-1)).toBe("negative");
    expect(returnTone(0)).toBe("");
    expect(returnTone(null)).toBe("");
  });
});

describe("formatElapsed", () => {
  it("switches to minutes past sixty seconds", () => {
    expect(formatElapsed(5_000)).toBe("5초");
    expect(formatElapsed(128_000)).toBe("2분 8초");
  });
});

describe("priceErrorLabel", () => {
  it("translates known failure kinds and falls back for unknown ones", () => {
    expect(priceErrorLabel("authentication")).toBe("인증 실패");
    expect(priceErrorLabel("not_configured")).toBe("가격 조회 미설정");
    expect(priceErrorLabel(null)).toBe("사유 미상");
  });
});

describe("describePricePerformance", () => {
  it("describes a buy against the entry snapshot", () => {
    const { basis, detail } = describePricePerformance(item());

    expect(basis).toContain("kis realtime 100원");
    expect(detail).toBe("그날 샀더라면 현재 +10.0%");
  });

  it("flips the wording for a sell recommendation", () => {
    expect(describePricePerformance(item({ action: "sell" })).detail).toBe(
      "그날 팔았더라면 현재 +10.0%",
    );
  });

  it("explains why an entry price is missing", () => {
    const { detail } = describePricePerformance(
      item({ entry_price: null, entry_error_kind: "authentication" }),
    );

    expect(detail).toBe("가격 미확인 (사유: 인증 실패)");
  });

  it("explains a missing latest price separately from a missing entry price", () => {
    const { detail } = describePricePerformance(
      item({ return_percent: null, latest_price: null, latest_error_kind: "rate_limit" }),
    );

    expect(detail).toBe("현재가 미확인 (사유: 요청 한도 초과)");
  });

  it("stays safe when no performance row exists for a recommendation", () => {
    expect(describePricePerformance(undefined).detail).toBe("가격 미확인");
  });
});
