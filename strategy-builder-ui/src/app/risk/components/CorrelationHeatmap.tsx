"use client";

import { ParentSize } from "@visx/responsive";
import type { StrategyCorrelation } from "@/lib/dashboard/analytics";

// Diverging scale: -1 (blue, anti-correlated) → 0 (grey) → +1 (red, moves
// together = concentration risk). Uses KR up=red convention for "positive".
function corrColor(v: number | null): string {
  if (v === null) return "#e2e8f0"; // slate-200 — undefined
  const clamped = Math.max(-1, Math.min(1, v));
  if (clamped >= 0) {
    // 0 → #f1f5f9, 1 → #ef4444
    const t = clamped;
    const r = Math.round(241 + (239 - 241) * t);
    const g = Math.round(245 + (68 - 245) * t);
    const b = Math.round(249 + (68 - 249) * t);
    return `rgb(${r},${g},${b})`;
  }
  const t = -clamped;
  const r = Math.round(241 + (59 - 241) * t);
  const g = Math.round(245 + (130 - 245) * t);
  const b = Math.round(249 + (246 - 249) * t);
  return `rgb(${r},${g},${b})`;
}

function shortLabel(s: string): string {
  return s.length > 10 ? `${s.slice(0, 9)}…` : s;
}

/** Fixed-size grid renderer — named export for deterministic render tests. */
export function CorrelationGrid({
  width,
  height,
  data,
}: {
  width: number;
  height: number;
  data: StrategyCorrelation;
}) {
  const n = data.strategies.length;
  const margin = { top: 8, right: 8, bottom: 70, left: 70 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);
  const cell = Math.max(1, Math.min(innerW / n, innerH / n));

  return (
    <svg width={width} height={height}>
      <g transform={`translate(${margin.left},${margin.top})`}>
        {data.matrix.map((row, i) =>
          row.map((v, j) => (
            <rect
              key={`${i}-${j}`}
              x={j * cell}
              y={i * cell}
              width={cell - 1}
              height={cell - 1}
              fill={corrColor(v)}
            >
              <title>
                {`${data.strategies[i]} × ${data.strategies[j]}: ${
                  v === null ? "n/a" : v.toFixed(2)
                }`}
              </title>
            </rect>
          )),
        )}
        {/* Row labels (left) */}
        {data.strategies.map((s, i) => (
          <text
            key={`r-${s}`}
            x={-4}
            y={i * cell + cell / 2}
            textAnchor="end"
            dominantBaseline="middle"
            fontSize={10}
            fill="#64748b"
          >
            {shortLabel(s)}
          </text>
        ))}
        {/* Column labels (bottom, rotated) */}
        {data.strategies.map((s, j) => (
          <text
            key={`c-${s}`}
            x={j * cell + cell / 2}
            y={n * cell + 4}
            textAnchor="end"
            dominantBaseline="middle"
            fontSize={10}
            fill="#64748b"
            transform={`rotate(-45, ${j * cell + cell / 2}, ${n * cell + 4})`}
          >
            {shortLabel(s)}
          </text>
        ))}
      </g>
    </svg>
  );
}

/** Per-strategy daily-PnL correlation heatmap — spots false diversification. */
export default function CorrelationHeatmap({
  data,
}: {
  data: StrategyCorrelation | undefined;
}) {
  const ready = data?.status === "ok" && data.strategies.length >= 2;
  return (
    <section
      aria-label="Strategy Correlation"
      className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
    >
      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        전략 상관 (일 PnL)
      </h3>
      <p className="text-xs text-slate-500">
        빨강 = 동반 상승/하락(집중위험) · 파랑 = 역상관 · 회색 = 미정의
      </p>
      {!ready ? (
        <div className="flex h-64 items-center justify-center text-sm text-slate-400">
          {data?.status === "insufficient_data"
            ? "전략 2개 이상·거래일 2일 이상 필요"
            : "거래 데이터 없음 — paper 체결 후 표시됩니다"}
        </div>
      ) : (
        <div className="mt-2 h-64">
          <ParentSize>
            {({ width, height }) =>
              width > 0 && height > 0 ? (
                <CorrelationGrid width={width} height={height} data={data} />
              ) : null
            }
          </ParentSize>
        </div>
      )}
    </section>
  );
}
