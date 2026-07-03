"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ChartCard from "@/components/dashboard/ChartCard";
import type {
  PortfolioEquityHistoryPoint,
  PortfolioMddStages,
  PortfolioStage,
} from "@/lib/dashboard/portfolio";
import { normalizeStage } from "@/lib/dashboard/portfolio";

// Series colors follow the repo chart conventions (/market charts palette).
const COLOR_TOTAL = "#245bee"; // --color-primary
const COLOR_TRACK_A = "#64748b";
const COLOR_TRACK_B = "#ef4444";
const COLOR_TRACK_C = "#0891b2";
const COLOR_MDD = "#9333ea";

// 단계 마커/임계선 톤 — StageBadge(에메랄드/앰버/오렌지/로즈)와 동일 계열.
const STAGE_COLORS: Record<PortfolioStage, string> = {
  NORMAL: "#10b981",
  REDUCE: "#f59e0b",
  HALT_NEW: "#f97316",
  FULL_STOP: "#e11d48",
};

const AXIS_TICK = { fontSize: 11 } as const;
const GRID_PROPS = {
  strokeDasharray: "3 3",
  stroke: "#e2e8f0",
  vertical: false,
} as const;

const EMPTY_LABEL = "배치 미가동 — equity 배치 가동 후 표시됩니다";

function shortDate(value: string | null): string {
  return value ? value.slice(5) : "";
}

function fmtKrwTick(v: unknown): string {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "-";
  if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(1)}억`;
  if (Math.abs(n) >= 1e4) return `${Math.round(n / 1e4).toLocaleString("ko-KR")}만`;
  return Math.round(n).toLocaleString("ko-KR");
}

function fmtKrwFull(v: unknown): string {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? `₩${Math.round(n).toLocaleString("ko-KR")}` : "-";
}

function fmtPct(v: unknown): string {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? `${n.toFixed(2)}%` : "-";
}

/** 단계 전환일 목록 — 직전 포인트와 단계가 달라진 날만 마커로 표시한다. */
export function stageTransitions(
  points: PortfolioEquityHistoryPoint[],
): { trade_date: string; stage: PortfolioStage }[] {
  const transitions: { trade_date: string; stage: PortfolioStage }[] = [];
  let previous: PortfolioStage | null = null;
  for (const point of points) {
    const stage = normalizeStage(point.stage);
    if (stage === null) continue;
    if (previous !== null && stage !== previous && point.trade_date) {
      transitions.push({ trade_date: point.trade_date, stage });
    }
    previous = stage;
  }
  return transitions;
}

/** ① 통합 자산 곡선 (90일): total + 트랙별 라인 + 단계 전환일 마커. */
export function EquityCurveChart({
  points,
}: {
  points: PortfolioEquityHistoryPoint[];
}) {
  const hasData = points.some((p) => p.total_equity !== null);
  const transitions = stageTransitions(points);
  return (
    <ChartCard
      title="통합 자산 곡선"
      subtitle="총자산 + 트랙 A/B/C 분해 · 세로선 = MDD 단계 전환일"
      isEmpty={!hasData}
      emptyLabel={EMPTY_LABEL}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="trade_date" tickFormatter={shortDate} tick={AXIS_TICK} />
          <YAxis
            domain={["auto", "auto"]}
            tick={AXIS_TICK}
            width={56}
            tickFormatter={fmtKrwTick}
          />
          <Tooltip formatter={(v) => fmtKrwFull(v)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {transitions.map((transition) => (
            <ReferenceLine
              key={`${transition.trade_date}-${transition.stage}`}
              x={transition.trade_date}
              stroke={STAGE_COLORS[transition.stage]}
              strokeDasharray="4 3"
              label={{
                value: transition.stage,
                position: "top",
                fontSize: 10,
                fill: STAGE_COLORS[transition.stage],
              }}
            />
          ))}
          <Line
            type="monotone"
            dataKey="total_equity"
            name="총자산"
            stroke={COLOR_TOTAL}
            strokeWidth={2.5}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="track_b_equity"
            name="트랙 B (주식)"
            stroke={COLOR_TRACK_B}
            strokeWidth={1.5}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="track_c_equity"
            name="트랙 C (선물)"
            stroke={COLOR_TRACK_C}
            strokeWidth={1.5}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="track_a_equity"
            name="트랙 A (코어)"
            stroke={COLOR_TRACK_A}
            strokeWidth={1.5}
            strokeDasharray="5 4"
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

/** ② 월간 MDD % 서브차트: 단계 임계선(−5/−8/−12%) 오버레이. */
export function MddStageChart({
  points,
  stages,
}: {
  points: PortfolioEquityHistoryPoint[];
  stages: PortfolioMddStages | null;
}) {
  const hasData = points.some((p) => p.monthly_mdd_pct !== null);
  // 배치의 monthly_mdd_pct와 config 임계는 모두 비율(-0.05 = -5%) —
  // 차트는 % 단위로 그리므로 데이터/임계를 함께 x100 환산한다. config
  // 부재 시 설계서 §7.1 기본(−5/−8/−12%)으로 폴백.
  const data = points.map((p) => ({
    ...p,
    monthly_mdd_pct:
      p.monthly_mdd_pct === null ? null : p.monthly_mdd_pct * 100,
  }));
  const reducePct = (stages?.reduce.threshold ?? -0.05) * 100;
  const haltNewPct = (stages?.halt_new.threshold ?? -0.08) * 100;
  const fullStopPct = (stages?.full_stop.threshold ?? -0.12) * 100;
  const thresholds: { pct: number; stage: PortfolioStage }[] = [
    { pct: reducePct, stage: "REDUCE" },
    { pct: haltNewPct, stage: "HALT_NEW" },
    { pct: fullStopPct, stage: "FULL_STOP" },
  ];
  return (
    <ChartCard
      title="월간 MDD (전체 자산 기준)"
      subtitle={`월초 대비 낙폭 % · 임계 ${Math.round(reducePct)}% / ${Math.round(haltNewPct)}% / ${Math.round(fullStopPct)}%`}
      isEmpty={!hasData}
      emptyLabel={EMPTY_LABEL}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="trade_date" tickFormatter={shortDate} tick={AXIS_TICK} />
          <YAxis
            domain={[
              (dataMin: number) =>
                Math.min(Number.isFinite(dataMin) ? dataMin : 0, fullStopPct) -
                1,
              0,
            ]}
            tick={AXIS_TICK}
            width={44}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip formatter={(v) => fmtPct(v)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={0} stroke="#94a3b8" />
          {thresholds.map((threshold) => (
            <ReferenceLine
              key={threshold.stage}
              y={threshold.pct}
              stroke={STAGE_COLORS[threshold.stage]}
              strokeDasharray="4 3"
              label={{
                value: `${threshold.stage} ${Math.round(threshold.pct)}%`,
                position: "insideBottomLeft",
                fontSize: 10,
                fill: STAGE_COLORS[threshold.stage],
              }}
            />
          ))}
          <Line
            type="monotone"
            dataKey="monthly_mdd_pct"
            name="월간 MDD"
            stroke={COLOR_MDD}
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
