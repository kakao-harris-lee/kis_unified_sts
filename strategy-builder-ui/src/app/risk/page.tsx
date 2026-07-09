"use client";

import {
  AlertTriangle,
  CircleDollarSign,
  Layers3,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";
import HeaderBar from "@/components/dashboard/HeaderBar";
import ErrorMessage from "@/components/dashboard/ErrorMessage";
import RefreshIndicator from "@/components/dashboard/RefreshIndicator";
import SymbolLabel from "@/components/dashboard/SymbolLabel";
import useQueryWithError from "@/hooks/dashboard/useQueryWithError";
import { useAssetClass } from "@/contexts/dashboard/AssetClassContext";
import { portfolioApi, reportsApi, tradingApi } from "@/lib/dashboard/api";
import type { FeedbackListResponse } from "@/lib/dashboard/reports";
import { QUERY_INTERVALS_MS } from "@/lib/dashboard/queryIntervals";
import type {
  PortfolioEquityHistory,
  PortfolioEquityLatest,
  PortfolioHedgeLatest,
} from "@/lib/dashboard/portfolio";
import type {
  RiskExposure,
  RiskStrategyExposure,
  RiskSymbolExposure,
} from "@/lib/dashboard/types";
import FeedbackSummaryCard from "./components/FeedbackSummaryCard";
import PortfolioEquityPanel from "./components/PortfolioEquityPanel";
import {
  EquityCurveChart,
  MddStageChart,
} from "./components/PortfolioEquityChart";
import RollingStatsChart from "./components/RollingStatsChart";
import UnderwaterChart from "./components/UnderwaterChart";

const EQUITY_HISTORY_DAYS = 90;

function fmtKrw(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `${v.toFixed(1)}%`;
}

function fmtDateTime(v?: string | null): string {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime())
    ? v
    : d.toLocaleString("ko-KR", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function pnlClass(v: number | null | undefined): string {
  return (v ?? 0) >= 0 ? "text-profit" : "text-loss";
}

function lossClass(v: number | null | undefined): string {
  return v !== null && v !== undefined && v !== 0
    ? "text-loss"
    : "text-slate-900 dark:text-slate-100";
}

function StatCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div className={`mt-1 truncate text-lg font-bold ${tone ?? "text-slate-900 dark:text-slate-100"}`}>
        {value}
      </div>
    </div>
  );
}

function StrategyTable({ rows }: { rows: RiskStrategyExposure[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">Strategy exposure by asset class and strategy</caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["자산", "전략", "포지션", "총노출", "순노출", "미실현", "Equity 대비"].map((h, i) => (
              <th
                key={h}
                scope="col"
                className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${i < 2 ? "text-left" : "text-right"}`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row) => (
            <tr
              key={`${row.asset_class}-${row.strategy}`}
              className="hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <td className="px-3 py-3 text-xs font-medium uppercase text-slate-500">
                {row.asset_class}
              </td>
              <td className="px-3 py-3 font-semibold text-slate-900 dark:text-slate-100">
                {row.strategy}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">{row.positions}</td>
              <td className="px-3 py-3 text-right tabular-nums">{fmtKrw(row.gross_exposure_krw)}</td>
              <td className="px-3 py-3 text-right tabular-nums">{fmtKrw(row.net_exposure_krw)}</td>
              <td className={`px-3 py-3 text-right tabular-nums font-semibold ${pnlClass(row.unrealized_pnl_krw)}`}>
                {fmtKrw(row.unrealized_pnl_krw)}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">
                {fmtPct(row.exposure_to_equity_pct)}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="px-3 py-8 text-center text-sm text-slate-500" colSpan={7}>
                No strategy exposure
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function SymbolTable({ rows }: { rows: RiskSymbolExposure[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">Symbol exposure and unrealized risk by position</caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["자산", "종목", "방향", "수량", "현재가", "노출", "미실현", "수익률", "전략"].map((h, i) => (
              <th
                key={h}
                scope="col"
                className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${i === 1 || i === 8 ? "text-left" : "text-right"}`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row) => (
            <tr
              key={`${row.asset_class}-${row.code}-${row.strategy}`}
              className="hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <td className="px-3 py-3 text-right text-xs font-medium uppercase text-slate-500">
                {row.asset_class}
              </td>
              <td className="px-3 py-3">
                <SymbolLabel
                  code={row.code}
                  name={row.name}
                  nameClassName="text-slate-900 dark:text-slate-100"
                />
              </td>
              <td className="px-3 py-3 text-right text-xs font-medium uppercase">
                {row.side}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">{row.quantity}</td>
              <td className="px-3 py-3 text-right tabular-nums">
                {row.current_price.toLocaleString("ko-KR")}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">
                {fmtKrw(row.signed_exposure_krw)}
              </td>
              <td className={`px-3 py-3 text-right tabular-nums font-semibold ${pnlClass(row.unrealized_pnl_krw)}`}>
                {fmtKrw(row.unrealized_pnl_krw)}
              </td>
              <td className={`px-3 py-3 text-right tabular-nums font-semibold ${pnlClass(row.pnl_pct)}`}>
                {fmtPct(row.pnl_pct)}
              </td>
              <td className="px-3 py-3 text-left text-xs text-slate-600 dark:text-slate-300">
                {row.strategy}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="px-3 py-8 text-center text-sm text-slate-500" colSpan={9}>
                No symbol exposure
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function RiskPage() {
  const { selectedAsset } = useAssetClass();
  const {
    data,
    isLoading,
    errorMessage,
    refetch,
    dataUpdatedAt,
    isFetching,
  } = useQueryWithError<RiskExposure>({
    queryKey: ["risk-exposure", selectedAsset],
    queryFn: () =>
      tradingApi.getRiskExposure({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.normal,
  });

  // 통합 자산 (Phase 3D) — 자산군 탭과 무관한 전체 계좌 합산 뷰.
  const {
    data: equityLatest,
    isLoading: equityLoading,
    refetch: refetchEquity,
  } = useQueryWithError<PortfolioEquityLatest>({
    queryKey: ["portfolio-equity"],
    queryFn: () => portfolioApi.getEquity().then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.normal,
  });
  const { data: equityHistory, refetch: refetchEquityHistory } =
    useQueryWithError<PortfolioEquityHistory>({
      queryKey: ["portfolio-equity-history", EQUITY_HISTORY_DAYS],
      queryFn: () =>
        portfolioApi
          .getEquityHistory({ days: EQUITY_HISTORY_DAYS })
          .then((r) => r.data),
      refetchInterval: QUERY_INTERVALS_MS.experiments,
    });
  // 헤지 어드바이저 (Phase 4B §6.2) — 순 β-노출 셀 전용, 권고 전용 표시.
  const { data: hedgeLatest, refetch: refetchHedge } =
    useQueryWithError<PortfolioHedgeLatest>({
      queryKey: ["portfolio-hedge"],
      queryFn: () => portfolioApi.getHedge().then((r) => r.data),
      refetchInterval: QUERY_INTERVALS_MS.normal,
    });

  // 성과 피드백 리포트 (Phase 6B §8) — 자산군 탭과 무관한 전 시스템 요약.
  // 엔진 미가동 시 빈 목록 → 카드가 empty state를 렌더한다.
  const { data: feedbackWeekly, isLoading: feedbackLoading } =
    useQueryWithError<FeedbackListResponse>({
      queryKey: ["feedback-reports", "weekly"],
      queryFn: () =>
        reportsApi
          .listFeedback({ kind: "weekly", limit: 8 })
          .then((r) => r.data),
      refetchInterval: QUERY_INTERVALS_MS.experiments,
    });
  const { data: feedbackMonthly } = useQueryWithError<FeedbackListResponse>({
    queryKey: ["feedback-reports", "monthly"],
    queryFn: () =>
      reportsApi.listFeedback({ kind: "monthly", limit: 1 }).then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.experiments,
  });
  const { data: feedbackQuarterly } = useQueryWithError<FeedbackListResponse>({
    queryKey: ["feedback-reports", "quarterly"],
    queryFn: () =>
      reportsApi
        .listFeedback({ kind: "quarterly", limit: 1 })
        .then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.experiments,
  });

  const portfolio = data?.portfolio;
  const equityPoints = equityHistory?.points ?? [];

  const handleRefresh = () => {
    refetch();
    refetchEquity();
    refetchEquityHistory();
    refetchHedge();
  };

  return (
    <>
      <HeaderBar />
      <div className="mx-auto max-w-[1400px] px-2 pb-24 pt-2 sm:px-4 lg:px-6 lg:pb-2">
        <div className="space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  Risk & Exposure
                </h1>
                <p className="text-sm text-slate-500">
                  {data ? `${data.asset_class} · ${fmtDateTime(data.generated_at)}` : selectedAsset}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <RefreshIndicator
                lastUpdated={dataUpdatedAt}
                isRefreshing={isFetching}
              />
              <button
                type="button"
                onClick={handleRefresh}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 focus-ring dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                aria-label="Refresh risk exposure"
              >
                <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          {errorMessage && (
            <ErrorMessage message={errorMessage} onRetry={() => refetch()} />
          )}

          {isLoading && !data ? (
            <div role="status" aria-label="Loading risk exposure" className="sr-only">
              Loading risk exposure
            </div>
          ) : null}

          {/* 통합 자산 카드 행 + MDD 단계 배지 (Phase 3D — 표시 전용)
              + 크로스에셋 순 β-노출 셀 (Phase 4B §6.2 — 권고 전용) */}
          <PortfolioEquityPanel
            data={equityLatest}
            isLoading={equityLoading}
            hedge={hedgeLatest}
          />

          {/* 통합 자산 곡선 + 월간 MDD 서브차트 (90일) */}
          <div className="grid gap-2 lg:grid-cols-2">
            <EquityCurveChart points={equityPoints} />
            <MddStageChart
              points={equityPoints}
              stages={equityLatest?.stages ?? null}
            />
          </div>

          {/* Underwater 낙폭 + 롤링 Sharpe (누적 최고점 대비 / 20 거래일, 90일) */}
          <div className="grid gap-2 lg:grid-cols-2">
            <UnderwaterChart points={equityPoints} />
            <RollingStatsChart points={equityPoints} />
          </div>

          {/* 성과 피드백 요약 (Phase 6B §8 — 표시 전용, 판정 자료) */}
          <FeedbackSummaryCard
            weekly={feedbackWeekly}
            monthly={feedbackMonthly}
            quarterly={feedbackQuarterly}
            isLoading={feedbackLoading}
          />

          <section className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            <StatCell
              label="Equity"
              value={isLoading && !portfolio ? "..." : fmtKrw(portfolio?.equity_krw)}
            />
            <StatCell
              label="Gross Exposure"
              value={isLoading && !portfolio ? "..." : fmtKrw(portfolio?.gross_exposure_krw)}
            />
            <StatCell
              label="Net Exposure"
              value={isLoading && !portfolio ? "..." : fmtKrw(portfolio?.net_exposure_krw)}
            />
            <StatCell
              label="Daily P&L"
              value={isLoading && !portfolio ? "..." : fmtKrw(portfolio?.daily_pnl_krw)}
              tone={pnlClass(portfolio?.daily_pnl_krw)}
            />
          </section>

          <section className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            <StatCell
              label="Cash"
              value={fmtKrw(portfolio?.cash_krw)}
            />
            <StatCell
              label="Exposure / Equity"
              value={fmtPct(portfolio?.exposure_to_equity_pct)}
            />
            <StatCell
              label="Open Positions"
              value={`${portfolio?.open_positions ?? 0}`}
            />
            <StatCell
              label="Daily Loss"
              value={fmtKrw(portfolio?.daily_loss_krw)}
              tone={lossClass(portfolio?.daily_loss_krw)}
            />
          </section>

          {data?.notes?.length ? (
            <div
              role="alert"
              className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
            >
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <div className="space-y-1 break-words">
                  {data.notes.map((note) => (
                    <div key={note}>{note}</div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers3 className="h-4 w-4 text-slate-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                  Strategy Exposure
                </h2>
              </div>
              <span className="text-sm text-slate-500">
                {data?.by_strategy.length ?? 0} rows
              </span>
            </div>
            <StrategyTable rows={data?.by_strategy ?? []} />
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CircleDollarSign className="h-4 w-4 text-slate-500" aria-hidden="true" />
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                  Symbol Exposure
                </h2>
              </div>
              <span className="text-sm text-slate-500">
                {data?.by_symbol.length ?? 0} rows
              </span>
            </div>
            <SymbolTable rows={data?.by_symbol ?? []} />
          </section>
        </div>
      </div>
    </>
  );
}
