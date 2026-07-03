import type { RiskBand } from "@/lib/dashboard/marketRisk";
import { normalizeBand } from "@/lib/dashboard/marketRisk";

// Band → tone maps for the Market Risk Score (roadmap §4.2). Full class
// strings so the Tailwind JIT can see them; risk severity ramps from calm
// (emerald) to critical (rose) — 상승/하락 색상(profit/loss)과는 별개의 상태색.

export const BAND_BADGE_CLASSES: Record<RiskBand, string> = {
  LOW: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  NEUTRAL: "bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-200",
  ELEVATED: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  HIGH: "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200",
  CRITICAL: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200",
};

// Saturated fills for the score gauge segments and the dark header chip.
export const BAND_FILL_CLASSES: Record<RiskBand, string> = {
  LOW: "bg-emerald-500",
  NEUTRAL: "bg-sky-500",
  ELEVATED: "bg-amber-500",
  HIGH: "bg-orange-500",
  CRITICAL: "bg-rose-600",
};

export const BAND_HEADER_CHIP_CLASSES: Record<RiskBand, string> = {
  LOW: "bg-emerald-700",
  NEUTRAL: "bg-sky-700",
  ELEVATED: "bg-amber-600",
  HIGH: "bg-orange-700",
  CRITICAL: "bg-rose-700",
};

const REGIME_BADGE_CLASSES: Record<string, string> = {
  RISK_ON:
    "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  NEUTRAL: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
  RISK_OFF: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200",
};

const UNKNOWN_BADGE =
  "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400";

export function RiskBandBadge({ band }: { band: string | null | undefined }) {
  const normalized = normalizeBand(band);
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold uppercase ${
        normalized ? BAND_BADGE_CLASSES[normalized] : UNKNOWN_BADGE
      }`}
    >
      {normalized ?? band ?? "N/A"}
    </span>
  );
}

export function RegimeBadge({ regime }: { regime: string | null | undefined }) {
  const key = (regime ?? "").trim().toUpperCase();
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold uppercase ${
        REGIME_BADGE_CLASSES[key] ?? UNKNOWN_BADGE
      }`}
    >
      {key || "N/A"}
    </span>
  );
}

export default RiskBandBadge;
