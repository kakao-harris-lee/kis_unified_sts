"use client";

import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  MarketRiskHistoryPoint,
  NightCloseSummary,
} from "@/lib/dashboard/marketRisk";
import { formatKstShort } from "@/lib/dashboard/format";

// Series colors follow the repo chart conventions (experiments page palette)
// and the Korean up/down tokens (--color-profit red / --color-loss blue).
const COLOR_SCORE = "#ef4444";
const COLOR_SCORE_EMA = "#ca8a04";
const COLOR_KOSPI = "#64748b";
const COLOR_CUM20 = "#2563eb";
const COLOR_BAR_POS = "#ef4444";
const COLOR_BAR_NEG = "#3b82f6";
const COLOR_BASIS = "#0891b2";
const COLOR_BASIS_MA = "#9333ea";

const AXIS_TICK = { fontSize: 11 } as const;
const GRID_PROPS = {
  strokeDasharray: "3 3",
  stroke: "#e2e8f0",
  vertical: false,
} as const;

function shortDate(value: string | null): string {
  return value ? value.slice(5) : "";
}

function fmtNum(v: unknown, digits = 2): string {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n.toFixed(digits) : "-";
}

function fmtQty(v: unknown): string {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? Math.round(n).toLocaleString("ko-KR") : "-";
}

export function ChartCard({
  title,
  subtitle,
  isEmpty,
  emptyLabel = "데이터 없음 — 수집/엔진 가동 후 표시됩니다",
  children,
}: {
  title: string;
  subtitle?: string;
  isEmpty: boolean;
  emptyLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      aria-label={title}
      className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
    >
      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        {title}
      </h3>
      {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      {isEmpty ? (
        <div className="flex h-64 items-center justify-center text-sm text-slate-400">
          {emptyLabel}
        </div>
      ) : (
        <div className="mt-2 h-64">{children}</div>
      )}
    </section>
  );
}

/** ① Risk score 90-day history with KOSPI close overlay (dual axis). */
export function ScoreHistoryChart({
  points,
}: {
  points: MarketRiskHistoryPoint[];
}) {
  const hasScore = points.some((p) => p.risk_score !== null);
  const hasKospi = points.some((p) => p.kospi_close !== null);
  return (
    <ChartCard
      title="Risk Score 이력 + KOSPI"
      subtitle="좌축: score(0–100) · 우축: KOSPI200 종가"
      isEmpty={!hasScore && !hasKospi}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="trade_date" tickFormatter={shortDate} tick={AXIS_TICK} />
          <YAxis yAxisId="score" domain={[0, 100]} tick={AXIS_TICK} width={36} />
          <YAxis
            yAxisId="kospi"
            orientation="right"
            domain={["auto", "auto"]}
            tick={AXIS_TICK}
            width={52}
          />
          <Tooltip formatter={(v) => fmtNum(v)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            yAxisId="score"
            type="monotone"
            dataKey="risk_score"
            name="Risk Score"
            stroke={COLOR_SCORE}
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            yAxisId="score"
            type="monotone"
            dataKey="risk_score_ema3"
            name="Score EMA3"
            stroke={COLOR_SCORE_EMA}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            connectNulls
          />
          <Line
            yAxisId="kospi"
            type="monotone"
            dataKey="kospi_close"
            name="KOSPI200"
            stroke={COLOR_KOSPI}
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

/** ② Foreign futures net-buy: daily bars + 20-day cumulative line. */
export function ForeignFuturesChart({
  points,
}: {
  points: MarketRiskHistoryPoint[];
}) {
  const hasData = points.some(
    (p) => p.fut_foreign_net_qty !== null || p.fut_foreign_net_qty_cum20 !== null,
  );
  return (
    <ChartCard
      title="외국인 선물 순매수 (20일 누적)"
      subtitle="막대: 일별 순매수 계약 · 선: 20일 누적"
      isEmpty={!hasData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={points}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="trade_date" tickFormatter={shortDate} tick={AXIS_TICK} />
          <YAxis tick={AXIS_TICK} width={64} tickFormatter={(v) => fmtQty(v)} />
          <Tooltip formatter={(v) => fmtQty(v)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={0} stroke="#94a3b8" />
          <Bar dataKey="fut_foreign_net_qty" name="일별 순매수" barSize={6}>
            {points.map((point, index) => (
              <Cell
                key={point.trade_date ?? index}
                fill={
                  (point.fut_foreign_net_qty ?? 0) >= 0
                    ? COLOR_BAR_POS
                    : COLOR_BAR_NEG
                }
              />
            ))}
          </Bar>
          <Line
            type="monotone"
            dataKey="fut_foreign_net_qty_cum20"
            name="20일 누적"
            stroke={COLOR_CUM20}
            strokeWidth={2}
            dot={false}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

/** ③ Basis deviation history (0 기준 콘탱고/백워데이션). */
export function BasisChart({ points }: { points: MarketRiskHistoryPoint[] }) {
  const hasData = points.some((p) => p.basis_dev !== null);
  return (
    <ChartCard
      title="베이시스 괴리 (이론가 대비)"
      subtitle="0 위 = 콘탱고(고평가) · 0 아래 = 백워데이션(저평가)"
      isEmpty={!hasData}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points}>
          <CartesianGrid {...GRID_PROPS} />
          <XAxis dataKey="trade_date" tickFormatter={shortDate} tick={AXIS_TICK} />
          <YAxis tick={AXIS_TICK} width={48} />
          <Tooltip formatter={(v) => fmtNum(v, 3)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={0} stroke="#94a3b8" />
          <Line
            type="monotone"
            dataKey="basis_dev"
            name="basis_dev"
            stroke={COLOR_BASIS}
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="basis_dev_ma5"
            name="5일 평균"
            stroke={COLOR_BASIS_MA}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

// ---------------------------------------------------------------------------
// ④ Night-signal tiles (야간 K200 선물 종가 + 미 선물/SOX 야간 등락)
// ---------------------------------------------------------------------------

function changeTone(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-slate-900 dark:text-slate-100";
  return v >= 0 ? "text-profit" : "text-loss";
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function Tile({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: string;
  tone?: string;
  sub?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div
        className={`mt-1 truncate text-lg font-bold tabular-nums ${
          tone ?? "text-slate-900 dark:text-slate-100"
        }`}
      >
        {value}
      </div>
      {sub && <div className="text-[11px] text-slate-400">{sub}</div>}
    </div>
  );
}

export function NightSignalTiles({
  nightClose,
  latestPoint,
}: {
  nightClose: NightCloseSummary;
  latestPoint: MarketRiskHistoryPoint | null;
}) {
  return (
    <section
      aria-label="Overnight signals"
      className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          야간 신호
        </h3>
        <span className="text-xs text-slate-500">
          {nightClose.available && nightClose.asof
            ? `야간 종가 ${formatKstShort(nightClose.asof)} KST${
                nightClose.status === "stale" ? " · stale" : ""
              }`
            : "야간 종가 미수집"}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        KRX 야간 K200 선물 마지막 체결(05:50–06:00 KST 캡처) + 미 선물/SOX 야간
        등락 — 장전(premarket) 산출의 입력.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Tile
          label="야간 K200 종가"
          value={
            nightClose.close !== null && nightClose.close !== undefined
              ? nightClose.close.toFixed(2)
              : "-"
          }
          sub={nightClose.product_code ?? undefined}
        />
        <Tile
          label="야간 베이시스"
          value={
            nightClose.mrkt_basis !== null && nightClose.mrkt_basis !== undefined
              ? nightClose.mrkt_basis.toFixed(2)
              : "-"
          }
          tone={changeTone(nightClose.mrkt_basis)}
        />
        <Tile
          label="야간 괴리율"
          value={fmtPct(nightClose.dprt)}
          tone={changeTone(nightClose.dprt)}
        />
        <Tile
          label="ES 야간"
          value={fmtPct(latestPoint?.es_ovn_ret)}
          tone={changeTone(latestPoint?.es_ovn_ret)}
        />
        <Tile
          label="NQ 야간"
          value={fmtPct(latestPoint?.nq_ovn_ret)}
          tone={changeTone(latestPoint?.nq_ovn_ret)}
        />
        <Tile
          label="SOX"
          value={fmtPct(latestPoint?.sox_ret)}
          tone={changeTone(latestPoint?.sox_ret)}
        />
      </div>
    </section>
  );
}
