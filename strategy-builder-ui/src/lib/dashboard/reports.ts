import { apiClient } from "./client";

// Unified performance feedback reports (Phase 6B) — read-only surface. Mirrors
// services/dashboard/routes/feedback.py response shapes. The report files are
// the source of truth; the API parses them leniently (candidate-key mapping),
// so every metric here is optional and may be null when the engine has not run
// or an older report omits it.

export type FeedbackKind = "weekly" | "monthly" | "quarterly";

// §8.2 판정 자료 — normalized quarterly verdict per track. "판정 자료일 뿐,
// 승격/강등 결정은 수동"이라는 게 이 프로젝트의 계약이다.
export type FeedbackVerdict =
  | "met"
  | "below"
  | "insufficient"
  | "deferred"
  | "unknown";

export interface FeedbackTrackMetrics {
  trades: number | null;
  win_rate: number | null;
  avg_win_loss: number | null;
  expectancy: number | null;
  realized_pnl: number | null;
  slippage: number | null;
}

export type FeedbackTracks = Record<"B" | "C" | "A", FeedbackTrackMetrics>;

export interface FeedbackReportRow {
  kind: FeedbackKind | string;
  period_label: string;
  generated_at: string | null;
  tracks: Partial<FeedbackTracks>;
  missing: string[];
  headline?: string | null;
  md_exists: boolean;
  error?: string;
  // monthly-only
  contribution?: string | null;
  // quarterly-only
  verdicts?: Partial<Record<"B" | "C" | "A", FeedbackVerdict | string>>;
}

export interface FeedbackListResponse {
  kind: FeedbackKind | string;
  count: number;
  reports: FeedbackReportRow[];
}

export interface FeedbackLatest {
  status: "ok" | "unavailable";
  source: "redis" | "scan" | null;
  kind?: FeedbackKind | string;
  period_label?: string;
  generated_at?: string | null;
  json_path?: string | null;
  md_path?: string | null;
  headline?: unknown;
}

export interface FeedbackReportDetail {
  kind: FeedbackKind | string;
  period_label: string;
  md_exists: boolean;
  report: Record<string, unknown>;
}

export const reportsApi = {
  listFeedback: (params: { kind: FeedbackKind; limit?: number }) =>
    apiClient.get<FeedbackListResponse>("/api/reports/feedback", { params }),
  getFeedbackLatest: () =>
    apiClient.get<FeedbackLatest>("/api/reports/feedback/latest"),
  getFeedbackReport: (kind: FeedbackKind, periodLabel: string) =>
    apiClient.get<FeedbackReportDetail>(
      `/api/reports/feedback/${kind}/${periodLabel}`,
    ),
};

// ---------------------------------------------------------------------------
// Verdict badge metadata (§8.2) — 판정 자료 색상. 충족 emerald / 미달 amber /
// insufficient·deferred muted. 상승/하락(profit/loss) 색과는 별개의 상태색.
// ---------------------------------------------------------------------------

export interface VerdictSpec {
  label: string;
  className: string;
}

export const VERDICT_SPECS: Record<FeedbackVerdict, VerdictSpec> = {
  met: {
    label: "충족",
    className:
      "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  },
  below: {
    label: "미달",
    className:
      "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  },
  insufficient: {
    label: "자료부족",
    className:
      "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  },
  deferred: {
    label: "유예",
    className:
      "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  },
  unknown: {
    label: "N/A",
    className:
      "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400",
  },
};

export function normalizeVerdict(
  raw: string | null | undefined,
): FeedbackVerdict {
  const key = (raw ?? "").trim().toLowerCase();
  if (key in VERDICT_SPECS) return key as FeedbackVerdict;
  return "unknown";
}
