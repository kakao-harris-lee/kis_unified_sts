"use client";

import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear, scaleTime } from "@visx/scale";
import { LinePath } from "@visx/shape";
import ChartCard from "@/components/dashboard/ChartCard";
import type { PortfolioEquityHistoryPoint } from "@/lib/dashboard/portfolio";

// SVG stroke는 var()를 신뢰성 있게 받지 못해 리터럴 hex 사용.
const COLOR_SHARPE = "#245bee"; // --color-primary (롤링 Sharpe)

const EMPTY_LABEL = "배치 미가동 — equity 배치 가동 후 표시됩니다";
const AXIS_TICK = { fontSize: 11, fill: "#94a3b8" } as const;

// 거래일 기준 롤링 창(기본 20 거래일 ≈ 1개월) + 연율화 상수(√252).
const DEFAULT_WINDOW = 20;
const TRADING_DAYS_PER_YEAR = 252;
const ANNUALIZE = Math.sqrt(TRADING_DAYS_PER_YEAR);

export interface RollingStatPoint {
  trade_date: string;
  /** 창 내 일수익률의 연율화 Sharpe (rf=0 가정). */
  sharpe: number;
  /** 창 내 일수익률 표준편차의 연율화 변동성 %. */
  vol_pct: number;
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function stddev(xs: number[], avg: number): number {
  // 표본 표준편차(ddof=1) — 창 크기가 작아 편의 보정.
  if (xs.length < 2) return 0;
  const variance =
    xs.reduce((a, b) => a + (b - avg) ** 2, 0) / (xs.length - 1);
  return Math.sqrt(variance);
}

/**
 * total_equity 시계열에서 일수익률을 파생해 거래일 기준 롤링 Sharpe/변동성을 계산.
 *
 * 백엔드에 일수익률 API가 없어 프론트에서 파생한다(Tier-1: 저비용·독립).
 * total_equity가 null인 포인트는 건너뛴다 — 결측일을 0으로 채우면 가짜 수익률
 * 스파이크가 생기므로 유효 포인트만 연속 거래일로 취급한다. 각 롤링 지표는 창이
 * 가득 찬(window 개) 시점부터 산출한다. Sharpe/변동성은 √252로 연율화(rf=0).
 */
export function computeRollingStats(
  points: PortfolioEquityHistoryPoint[],
  window: number = DEFAULT_WINDOW,
): RollingStatPoint[] {
  // (date, equity) 유효 시퀀스만 추출.
  const seq: { date: string; equity: number }[] = [];
  for (const p of points) {
    if (p.trade_date === null || p.total_equity === null || p.total_equity <= 0)
      continue;
    seq.push({ date: p.trade_date, equity: p.total_equity });
  }
  if (seq.length < 2) return [];

  // 일수익률 (인접 유효 포인트 간). returns[i]는 seq[i+1] 날짜에 귀속.
  const returns: { date: string; ret: number }[] = [];
  for (let i = 1; i < seq.length; i += 1) {
    returns.push({
      date: seq[i].date,
      ret: seq[i].equity / seq[i - 1].equity - 1,
    });
  }
  if (returns.length < window) return [];

  const result: RollingStatPoint[] = [];
  for (let i = window - 1; i < returns.length; i += 1) {
    const windowRets = returns.slice(i - window + 1, i + 1).map((r) => r.ret);
    const avg = mean(windowRets);
    const sd = stddev(windowRets, avg);
    const sharpe = sd > 0 ? (avg / sd) * ANNUALIZE : 0;
    const vol_pct = sd * ANNUALIZE * 100;
    result.push({ trade_date: returns[i].date, sharpe, vol_pct });
  }
  return result;
}

function fmtSharpe(v: number): string {
  return v.toFixed(1);
}

function shortDate(value: string): string {
  return value.slice(5);
}

/** 고정 width/height SVG 렌더러 — 테스트에서 ParentSize 없이 직접 렌더 가능. */
export function RollingStatsSvg({
  width,
  height,
  data,
}: {
  width: number;
  height: number;
  data: RollingStatPoint[];
}) {
  const margin = { top: 8, right: 8, bottom: 24, left: 44 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);

  const xScale = scaleTime({
    domain: [
      new Date(data[0].trade_date),
      new Date(data[data.length - 1].trade_date),
    ],
    range: [0, innerW],
  });
  // Sharpe 스케일 (좌축) — 0을 포함해 부호 전환이 보이도록.
  const sharpeVals = data.map((d) => d.sharpe);
  const yScale = scaleLinear({
    domain: [Math.min(0, ...sharpeVals), Math.max(0, ...sharpeVals)],
    range: [innerH, 0],
    nice: true,
  });

  return (
    <svg width={width} height={height}>
      <Group left={margin.left} top={margin.top}>
        <LinePath
          data={data}
          x={(d) => xScale(new Date(d.trade_date)) ?? 0}
          y={(d) => yScale(d.sharpe) ?? 0}
          curve={curveMonotoneX}
          stroke={COLOR_SHARPE}
          strokeWidth={1.5}
        />
        <AxisLeft
          scale={yScale}
          numTicks={4}
          tickFormat={(v) => fmtSharpe(Number(v))}
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

/** 롤링 Sharpe 차트 (20 거래일 창, √252 연율화) — regime 분류기 없이도 성과 추세 관찰. */
export default function RollingStatsChart({
  points,
}: {
  points: PortfolioEquityHistoryPoint[];
}) {
  const data = computeRollingStats(points);
  return (
    <ChartCard
      title="롤링 Sharpe (20 거래일)"
      subtitle="일수익률 파생 · √252 연율화 · rf=0 · equity 곡선 기반"
      isEmpty={data.length === 0}
      emptyLabel={EMPTY_LABEL}
    >
      <ParentSize>
        {({ width, height }) =>
          width > 0 && height > 0 ? (
            <RollingStatsSvg width={width} height={height} data={data} />
          ) : null
        }
      </ParentSize>
    </ChartCard>
  );
}
