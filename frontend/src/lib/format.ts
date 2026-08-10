import type { PerformanceItem, PriceErrorKind } from "./types";

const PRICE_ERROR_LABELS: Record<PriceErrorKind, string> = {
  not_configured: "가격 조회 미설정",
  transport: "네트워크 오류",
  authentication: "인증 실패",
  rate_limit: "요청 한도 초과",
  server: "서버 오류",
  invalid_ticker: "종목코드 오류",
  invalid_payload: "응답 형식 오류",
  not_found: "가격 정보 없음",
};

export function priceErrorLabel(kind: PriceErrorKind | null): string {
  return kind ? (PRICE_ERROR_LABELS[kind] ?? kind) : "사유 미상";
}

/**
 * Article URLs come from external providers, so only http(s) links are rendered
 * as navigable hrefs.
 */
export function safeHref(value: string): string {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "#";
  } catch {
    return "#";
  }
}

export function formatKst(value: string | null): string {
  if (!value) return "KST 시각 미확인";
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  })
    .formatToParts(new Date(value))
    .reduce<Record<string, string>>(
      (result, part) => ({ ...result, [part.type]: part.value }),
      {},
    );
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute} KST`;
}

export function formatElapsed(milliseconds: number): string {
  const seconds = Math.floor(milliseconds / 1000);
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes}분 ${seconds % 60}초` : `${seconds}초`;
}

export function formatPercent(value: number | null): string {
  if (value === null) return "-";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

export function returnTone(value: number | null): "" | "positive" | "negative" {
  if (value === null) return "";
  if (value > 0) return "positive";
  if (value < 0) return "negative";
  return "";
}

export interface PricePerformanceText {
  basis: string | null;
  detail: string;
}

export function describePricePerformance(
  item: PerformanceItem | undefined,
): PricePerformanceText {
  if (!item) return { basis: null, detail: "가격 미확인" };
  if (item.entry_price === null) {
    return {
      basis: null,
      detail: `가격 미확인 (사유: ${priceErrorLabel(item.entry_error_kind)})`,
    };
  }
  if (item.return_percent === null) {
    return {
      basis: null,
      detail: `현재가 미확인 (사유: ${priceErrorLabel(item.latest_error_kind)})`,
    };
  }
  const direction =
    item.action === "sell" ? "그날 팔았더라면 현재" : "그날 샀더라면 현재";
  return {
    basis: `추천 기준: ${item.entry_provider ?? "-"} ${item.entry_basis ?? "-"} ${item.entry_price}원 (${formatKst(item.entry_observed_at)})`,
    detail: `${direction} ${formatPercent(item.return_percent)}`,
  };
}
