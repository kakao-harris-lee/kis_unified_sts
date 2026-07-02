"use client";

import { RISK_BANDS, normalizeBand } from "@/lib/dashboard/marketRisk";
import { BAND_FILL_CLASSES } from "@/components/dashboard/RiskBandBadge";

// Banded 0–100 score meter. Each §4.2 band renders as a colored segment; the
// current score is a marker line. Non-active segments are dimmed so the
// active band reads at a glance (identity is also labeled — not color-alone).
export default function ScoreGauge({
  score,
  band,
}: {
  score: number | null;
  band: string | null;
}) {
  const activeBand = normalizeBand(band);
  const clamped =
    score === null ? null : Math.max(0, Math.min(100, score));

  return (
    <div
      role="img"
      aria-label={
        clamped === null
          ? "Market risk score unavailable"
          : `Market risk score ${clamped.toFixed(1)} of 100, band ${activeBand ?? "unknown"}`
      }
      className="w-full"
    >
      <div className="relative">
        <div className="flex h-3 w-full overflow-hidden rounded-full">
          {RISK_BANDS.map((spec) => (
            <div
              key={spec.band}
              className={`${BAND_FILL_CLASSES[spec.band]} ${
                activeBand && activeBand !== spec.band ? "opacity-30" : ""
              } h-full border-r-2 border-white last:border-r-0 dark:border-slate-900`}
              style={{ width: `${spec.max - spec.min + 1}%` }}
            />
          ))}
        </div>
        {clamped !== null && (
          <div
            aria-hidden="true"
            className="absolute -top-1 h-5 w-0.5 -translate-x-1/2 rounded bg-slate-900 dark:bg-slate-100"
            style={{ left: `${clamped}%` }}
          />
        )}
      </div>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-slate-400">
        <span>0</span>
        <span>30</span>
        <span>55</span>
        <span>70</span>
        <span>85</span>
        <span>100</span>
      </div>
    </div>
  );
}
