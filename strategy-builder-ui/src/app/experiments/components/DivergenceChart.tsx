"use client";

import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear, scaleTime } from "@visx/scale";
import { LinePath } from "@visx/shape";
import type { DivergencePoint } from "@/lib/api/experiments";

const COLOR_BACKTEST = "#64748b"; // slate — the expected (OOS) baseline
const COLOR_PAPER = "#245bee"; // --color-primary — realized paper
const AXIS_TICK = { fontSize: 11, fill: "#94a3b8" } as const;

function shortDate(value: string): string {
  return value.slice(5);
}

function fmtPct(v: number): string {
  return `${v.toFixed(0)}%`;
}

/** Fixed-size SVG — named export for deterministic render tests. */
export function DivergenceSvg({
  width,
  height,
  points,
}: {
  width: number;
  height: number;
  points: DivergencePoint[];
}) {
  const margin = { top: 8, right: 8, bottom: 24, left: 44 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);

  const xScale = scaleTime({
    domain: [
      new Date(points[0].trade_date),
      new Date(points[points.length - 1].trade_date),
    ],
    range: [0, innerW],
  });
  const vals = points.flatMap((p) => [p.backtest_cum_pct, p.paper_cum_pct]);
  const yScale = scaleLinear({
    domain: [Math.min(0, ...vals), Math.max(0, ...vals)],
    range: [innerH, 0],
    nice: true,
  });

  return (
    <svg width={width} height={height}>
      <Group left={margin.left} top={margin.top}>
        <LinePath
          data={points}
          x={(d) => xScale(new Date(d.trade_date)) ?? 0}
          y={(d) => yScale(d.backtest_cum_pct) ?? 0}
          curve={curveMonotoneX}
          stroke={COLOR_BACKTEST}
          strokeWidth={1.5}
          strokeDasharray="4 3"
        />
        <LinePath
          data={points}
          x={(d) => xScale(new Date(d.trade_date)) ?? 0}
          y={(d) => yScale(d.paper_cum_pct) ?? 0}
          curve={curveMonotoneX}
          stroke={COLOR_PAPER}
          strokeWidth={1.5}
        />
        <AxisLeft
          scale={yScale}
          numTicks={4}
          tickFormat={(v) => fmtPct(Number(v))}
          tickLabelProps={() => AXIS_TICK}
          stroke="#cbd5e1"
          tickStroke="#cbd5e1"
        />
        <AxisBottom
          top={innerH}
          scale={xScale}
          numTicks={5}
          tickFormat={(d) => shortDate((d as Date).toISOString().slice(0, 10))}
          tickLabelProps={() => AXIS_TICK}
          stroke="#cbd5e1"
          tickStroke="#cbd5e1"
        />
      </Group>
    </svg>
  );
}

/**
 * Backtest-vs-paper cumulative-return divergence over time. Dashed slate =
 * expected (backtest OOS baseline), solid blue = realized paper. The gap is the
 * live drift the operator watches — QuantConnect "Live Reconciliation"-style.
 */
export default function DivergenceChart({
  points,
  status,
}: {
  points: DivergencePoint[];
  status: string;
}) {
  const latest = points.length ? points[points.length - 1] : null;
  return (
    <section
      aria-label="Backtest vs Paper Divergence"
      className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          백테스트 vs 페이퍼 divergence
        </h3>
        {latest ? (
          <span
            className={`text-xs font-medium ${
              Math.abs(latest.divergence_pct) > 5
                ? "text-loss"
                : "text-slate-500"
            }`}
            title="페이퍼 누적수익 − 백테스트 누적수익 (최신)"
          >
            Δ {latest.divergence_pct > 0 ? "+" : ""}
            {latest.divergence_pct.toFixed(1)}%
          </span>
        ) : null}
      </div>
      <p className="text-xs text-slate-500">
        점선 = 백테스트(기대) · 실선 = 페이퍼(실현) · 누적수익 % · 일별
      </p>
      {points.length === 0 ? (
        <div className="flex h-64 items-center justify-center text-sm text-slate-400">
          {status === "no_report"
            ? "백테스트 리포트 없음 — 실험 실행 후 표시됩니다"
            : "겹치는 페이퍼·백테스트 구간 없음"}
        </div>
      ) : (
        <div className="mt-2 h-64">
          <ParentSize>
            {({ width, height }) =>
              width > 0 && height > 0 ? (
                <DivergenceSvg width={width} height={height} points={points} />
              ) : null
            }
          </ParentSize>
        </div>
      )}
    </section>
  );
}
