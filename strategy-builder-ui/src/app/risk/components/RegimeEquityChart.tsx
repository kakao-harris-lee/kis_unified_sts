"use client";

import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear, scaleTime } from "@visx/scale";
import { Bar, LinePath } from "@visx/shape";
import ChartCard from "@/components/dashboard/ChartCard";
import type { PortfolioEquityHistoryPoint } from "@/lib/dashboard/portfolio";
import type { MarketRiskHistoryPoint } from "@/lib/dashboard/marketRisk";

const COLOR_EQUITY = "#245bee"; // --color-primary
const EMPTY_LABEL = "배치 미가동 — equity·regime 배치 가동 후 표시됩니다";
const AXIS_TICK = { fontSize: 11, fill: "#94a3b8" } as const;

// Regime → background band color. unified_regime values (RISK_ON/NEUTRAL/RISK_OFF
// and HAR-RV-style trend/chop labels) map to a calm→alarm ramp; unknown = none.
const REGIME_FILL: Record<string, string> = {
  RISK_ON: "#22c55e",
  BULL: "#22c55e",
  TREND: "#22c55e",
  NEUTRAL: "#f59e0b",
  CHOP: "#f59e0b",
  RANGE: "#f59e0b",
  RISK_OFF: "#ef4444",
  BEAR: "#ef4444",
  CRISIS: "#ef4444",
};

function regimeFill(regime: string | null): string | null {
  if (!regime) return null;
  return REGIME_FILL[regime.toUpperCase()] ?? null;
}

export interface RegimeEquityPoint {
  trade_date: string;
  total_equity: number;
  regime: string | null;
}

/**
 * Join equity history and market-risk history on trade_date. Equity is the
 * base series (only days with equity render); regime is looked up per day and
 * may be null (no band shaded for that day).
 */
export function joinRegimeEquity(
  equity: PortfolioEquityHistoryPoint[],
  regimeHistory: MarketRiskHistoryPoint[],
): RegimeEquityPoint[] {
  const regimeByDate = new Map<string, string | null>();
  for (const r of regimeHistory) {
    if (r.trade_date) regimeByDate.set(r.trade_date, r.unified_regime);
  }
  const out: RegimeEquityPoint[] = [];
  for (const p of equity) {
    if (p.trade_date === null || p.total_equity === null) continue;
    out.push({
      trade_date: p.trade_date,
      total_equity: p.total_equity,
      regime: regimeByDate.get(p.trade_date) ?? null,
    });
  }
  return out;
}

function shortDate(value: string): string {
  return value.slice(5);
}

function fmtKrwTick(v: number): string {
  if (Math.abs(v) >= 1e8) return `${(v / 1e8).toFixed(1)}억`;
  if (Math.abs(v) >= 1e4) return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만`;
  return Math.round(v).toLocaleString("ko-KR");
}

/** Contiguous regime spans → background bands (merge adjacent equal regimes). */
export function regimeSpans(
  data: RegimeEquityPoint[],
): { start: string; end: string; regime: string }[] {
  const spans: { start: string; end: string; regime: string }[] = [];
  for (const p of data) {
    if (!p.regime) continue;
    const last = spans[spans.length - 1];
    if (last && last.regime === p.regime) {
      last.end = p.trade_date;
    } else {
      spans.push({ start: p.trade_date, end: p.trade_date, regime: p.regime });
    }
  }
  return spans;
}

/** Fixed-size SVG renderer — named export so tests render it without ParentSize. */
export function RegimeEquitySvg({
  width,
  height,
  data,
}: {
  width: number;
  height: number;
  data: RegimeEquityPoint[];
}) {
  const margin = { top: 8, right: 8, bottom: 24, left: 52 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);

  const xScale = scaleTime({
    domain: [
      new Date(data[0].trade_date),
      new Date(data[data.length - 1].trade_date),
    ],
    range: [0, innerW],
  });
  const equities = data.map((d) => d.total_equity);
  const yScale = scaleLinear({
    domain: [Math.min(...equities), Math.max(...equities)],
    range: [innerH, 0],
    nice: true,
  });

  const spans = regimeSpans(data);

  return (
    <svg width={width} height={height}>
      <Group left={margin.left} top={margin.top}>
        {spans.map((span, i) => {
          const fill = regimeFill(span.regime);
          if (!fill) return null;
          const x0 = xScale(new Date(span.start)) ?? 0;
          const x1 = xScale(new Date(span.end)) ?? 0;
          return (
            <Bar
              key={`${span.regime}-${i}`}
              x={x0}
              y={0}
              width={Math.max(1, x1 - x0)}
              height={innerH}
              fill={fill}
              fillOpacity={0.12}
            />
          );
        })}
        <LinePath
          data={data}
          x={(d) => xScale(new Date(d.trade_date)) ?? 0}
          y={(d) => yScale(d.total_equity) ?? 0}
          curve={curveMonotoneX}
          stroke={COLOR_EQUITY}
          strokeWidth={1.5}
        />
        <AxisLeft
          scale={yScale}
          numTicks={4}
          tickFormat={(v) => fmtKrwTick(Number(v))}
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

/** 자산 곡선 + regime 배경 밴드 — 초록=위험선호, 주황=중립, 빨강=위험회피. */
export default function RegimeEquityChart({
  equity,
  regimeHistory,
}: {
  equity: PortfolioEquityHistoryPoint[];
  regimeHistory: MarketRiskHistoryPoint[];
}) {
  const data = joinRegimeEquity(equity, regimeHistory);
  return (
    <ChartCard
      title="자산 곡선 · Regime 오버레이"
      subtitle="배경 = 통합 레짐(초록 위험선호 / 주황 중립 / 빨강 위험회피) · 일별"
      isEmpty={data.length === 0}
      emptyLabel={EMPTY_LABEL}
    >
      <ParentSize>
        {({ width, height }) =>
          width > 0 && height > 0 ? (
            <RegimeEquitySvg width={width} height={height} data={data} />
          ) : null
        }
      </ParentSize>
    </ChartCard>
  );
}
