export type RecommendationAction =
  | "strong_buy"
  | "buy"
  | "hold"
  | "sell"
  | "strong_sell";

export type PriceErrorKind =
  | "not_configured"
  | "transport"
  | "authentication"
  | "rate_limit"
  | "server"
  | "invalid_ticker"
  | "invalid_payload"
  | "not_found";

export interface StageCounts {
  input_count: number;
  accepted_count: number;
  rejected_count: number;
}

export interface EventQuote {
  paragraph_index: number;
  quote: string;
}

export interface EventEvidence {
  event_title: string;
  source_url: string;
  quotes: EventQuote[];
}

export interface AnalysisItem {
  id: string;
  source: string;
  title: string;
  status: string;
  summary: string | null;
  event_titles: string[];
  event_evidence: EventEvidence[];
  relevance: number | null;
  importance: number | null;
  credibility: number | null;
  reasons: string[];
  validation_status: string | null;
}

export interface ImpactDiagnostics {
  failed_extraction_batches: number;
  malformed_extraction_items: number;
  events_without_impact_observations: number;
  total_impact_observations: number;
  eligible_impact_observations: number;
  unresolved_company_exclusions: number;
  missing_company_identity_exclusions: number;
  review_not_verified_exclusions: number;
  unknown_direction_exclusions: number;
  scored_company_count: number;
}

export interface NewsCard {
  source: string;
  title: string;
  excerpt: string;
  url: string;
}

export interface RecommendationRow {
  company_name: string;
  ticker: string | null;
  score: number;
  action: RecommendationAction;
  reason_code: string;
  recommendation_index: number;
}

export interface DashboardRunResult {
  run_id: string;
  news_cards: NewsCard[];
  recommendations: RecommendationRow[];
  analyses: AnalysisItem[];
  statistics: { impact_diagnostics: ImpactDiagnostics | null };
  stage_counts: Record<string, StageCounts> | null;
}

export interface DashboardEvent {
  type: string;
  message: string;
  active_stage: string | null;
  node?: string;
  analyses: AnalysisItem[];
  stage_counts?: Record<string, StageCounts> | null;
  failure_stage?: string | null;
  failure_attempts?: number | null;
  error_type?: string | null;
}

export interface PerformanceItem {
  run_id: string;
  recommendation_index: number;
  company_name: string;
  ticker: string;
  action: "buy" | "sell";
  entry_price: number | null;
  entry_provider: string | null;
  entry_basis: string | null;
  entry_observed_at: string | null;
  entry_error_kind: PriceErrorKind | null;
  latest_price: number | null;
  latest_observed_at: string | null;
  latest_error_kind: PriceErrorKind | null;
  return_percent: number | null;
}

export interface PerformanceSummary {
  confirmed_count: number;
  unavailable_count: number;
  buy_count: number;
  sell_count: number;
  positive_win_rate: number | null;
  mean_return_percent: number | null;
  median_return_percent: number | null;
  latest_observed_at: string | null;
}

export interface PerformanceResponse {
  items: PerformanceItem[];
  summary: PerformanceSummary;
  evaluated_at: string;
}

export interface RunHistoryItem {
  run_id: string;
  observed_at: string;
  items: PerformanceItem[];
  summary: PerformanceSummary;
}

export interface RunHistoryResponse {
  runs: RunHistoryItem[];
  evaluated_at: string;
}

export const EMPTY_SUMMARY: PerformanceSummary = {
  confirmed_count: 0,
  unavailable_count: 0,
  buy_count: 0,
  sell_count: 0,
  positive_win_rate: null,
  mean_return_percent: null,
  median_return_percent: null,
  latest_observed_at: null,
};
