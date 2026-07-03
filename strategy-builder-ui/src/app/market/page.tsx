"use client";

import { AlertTriangle, Gauge, RefreshCcw } from "lucide-react";
import HeaderBar from "@/components/dashboard/HeaderBar";
import ErrorMessage from "@/components/dashboard/ErrorMessage";
import RefreshIndicator from "@/components/dashboard/RefreshIndicator";
import RiskBandBadge, {
  RegimeBadge,
} from "@/components/dashboard/RiskBandBadge";
import useQueryWithError from "@/hooks/dashboard/useQueryWithError";
import { marketRiskApi, portfolioApi } from "@/lib/dashboard/api";
import type {
  MarketRiskHistory,
  MarketRiskLatest,
} from "@/lib/dashboard/marketRisk";
import type {
  PortfolioHedgeHistory,
  PortfolioHedgeLatest,
} from "@/lib/dashboard/portfolio";
import { QUERY_INTERVALS_MS } from "@/lib/dashboard/queryIntervals";
import { formatKstDateTime } from "@/lib/dashboard/format";
import ScoreGauge from "./components/ScoreGauge";
import ComponentBreakdown from "./components/ComponentBreakdown";
import TrackResponsePanel from "./components/TrackResponsePanel";
import HedgeAdvisorCard from "./components/HedgeAdvisorCard";
import {
  BasisChart,
  ForeignFuturesChart,
  NightSignalTiles,
  ScoreHistoryChart,
} from "./components/MarketCharts";

const HISTORY_DAYS = 90;
const HEDGE_HISTORY_DAYS = 30;

function fmtScore(v: number | null | undefined): string {
  return v === null || v === undefined ? "-" : v.toFixed(1);
}

function fmtDelta(v: number | null | undefined): string {
  if (v === null || v === undefined) return "Δ -";
  return `Δ ${v >= 0 ? "+" : ""}${v.toFixed(1)}`;
}

function deltaTone(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-slate-500";
  // 위험도 방향 톤: 상승(악화)=rose, 하락(완화)=emerald.
  return v >= 0
    ? "text-rose-600 dark:text-rose-400"
    : "text-emerald-600 dark:text-emerald-400";
}

function coveragePct(v: number | null | undefined): string {
  return v === null || v === undefined ? "-" : `${(v * 100).toFixed(0)}%`;
}

export default function MarketPage() {
  const {
    data: latest,
    isLoading: latestLoading,
    errorMessage: latestError,
    refetch: refetchLatest,
    dataUpdatedAt,
    isFetching,
  } = useQueryWithError<MarketRiskLatest>({
    queryKey: ["market-risk"],
    queryFn: () => marketRiskApi.getLatest().then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.normal,
  });

  const { data: history, refetch: refetchHistory } =
    useQueryWithError<MarketRiskHistory>({
      queryKey: ["market-risk-history", HISTORY_DAYS],
      queryFn: () =>
        marketRiskApi.getHistory({ days: HISTORY_DAYS }).then((r) => r.data),
      refetchInterval: QUERY_INTERVALS_MS.experiments,
    });

  // 헤지 어드바이저 (Phase 4B) — 권고 전용, 자동 주문 없음.
  const {
    data: hedge,
    isLoading: hedgeLoading,
    refetch: refetchHedge,
  } = useQueryWithError<PortfolioHedgeLatest>({
    queryKey: ["portfolio-hedge"],
    queryFn: () => portfolioApi.getHedge().then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.normal,
  });
  const { data: hedgeHistory, refetch: refetchHedgeHistory } =
    useQueryWithError<PortfolioHedgeHistory>({
      queryKey: ["portfolio-hedge-history", HEDGE_HISTORY_DAYS],
      queryFn: () =>
        portfolioApi
          .getHedgeHistory({ days: HEDGE_HISTORY_DAYS })
          .then((r) => r.data),
      refetchInterval: QUERY_INTERVALS_MS.experiments,
    });

  const risk = latest?.risk ?? null;
  const unavailable = latest !== undefined && latest.status === "unavailable";
  const points = history?.points ?? [];
  const latestPoint = points.length > 0 ? points[points.length - 1] : null;

  const handleRefresh = () => {
    refetchLatest();
    refetchHistory();
    refetchHedge();
    refetchHedgeHistory();
  };

  return (
    <>
      <HeaderBar />
      <div className="mx-auto max-w-[1400px] px-2 pb-24 pt-2 sm:px-4 lg:px-6 lg:pb-2">
        <div className="space-y-5">
          {/* 페이지 헤더 */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Gauge className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  Market Risk &amp; Structure
                </h1>
                <p className="text-sm text-slate-500">
                  {risk
                    ? `${risk.kind ?? "-"} · ${formatKstDateTime(risk.asof, "-")} KST`
                    : "Market Risk Score 투명성 보드"}
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
                className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                aria-label="Refresh market risk"
              >
                <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          {latestError && (
            <ErrorMessage message={latestError} onRetry={handleRefresh} />
          )}

          {latestLoading && !latest ? (
            <div
              role="status"
              aria-label="Loading market risk"
              className="sr-only"
            >
              Loading market risk
            </div>
          ) : null}

          {/* 엔진 미발행 / degraded / stale 경고 배너 */}
          {unavailable && (
            <div
              role="status"
              className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
            >
              Market Risk 엔진이 아직 발행하지 않았습니다 (
              <code className="text-xs">{latest?.source}</code> 부재). 엔진 가동
              후 score·분해·차트가 채워집니다.
            </div>
          )}
          {risk?.degraded && (
            <div
              role="alert"
              className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
            >
              <div className="flex items-start gap-2">
                <AlertTriangle
                  className="mt-0.5 h-4 w-4 shrink-0"
                  aria-hidden="true"
                />
                <div>
                  <span className="font-bold">DEGRADED</span> — 커버리지{" "}
                  {coveragePct(risk.coverage_ratio)}
                  {risk.missing_components.length > 0 && (
                    <>
                      {" "}
                      · 결측: {risk.missing_components.join(", ")}
                    </>
                  )}
                  <span className="ml-1">
                    (enforcement 미사용 — fail-open)
                  </span>
                </div>
              </div>
            </div>
          )}
          {risk && !risk.degraded && risk.stale && (
            <div
              role="alert"
              className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
            >
              마지막 산출이 오래되었습니다 (
              {formatKstDateTime(risk.asof, "-")} KST) — 엔진 스케줄을
              확인하세요.
            </div>
          )}

          {/* 스코어 게이지 헤더 */}
          <section
            aria-label="Market risk score"
            className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
              <div className="flex items-end gap-3">
                <div>
                  <div className="text-xs font-medium uppercase text-slate-500">
                    Risk Score
                  </div>
                  <div className="text-4xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                    {fmtScore(risk?.score)}
                  </div>
                </div>
                <div className="pb-1">
                  <div
                    className={`text-sm font-semibold tabular-nums ${deltaTone(risk?.score_delta_1d)}`}
                  >
                    {fmtDelta(risk?.score_delta_1d)}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    전일 close{" "}
                    {risk?.prev_close_score !== null &&
                    risk?.prev_close_score !== undefined
                      ? risk.prev_close_score.toFixed(1)
                      : "-"}
                  </div>
                </div>
              </div>
              <div className="min-w-0 flex-1">
                <ScoreGauge
                  score={risk?.score ?? null}
                  band={risk?.band ?? null}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <RiskBandBadge band={risk?.band} />
                <RegimeBadge regime={risk?.regime} />
                <span className="text-xs text-slate-500">
                  EMA3 {fmtScore(risk?.score_ema3)} · 커버리지{" "}
                  {coveragePct(risk?.coverage_ratio)}
                </span>
              </div>
            </div>
          </section>

          {/* 구성요소 분해 */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                구성요소 분해
              </h2>
              <span className="text-sm text-slate-500">
                왜 이 점수인가 — sub-score × 가중치 = 기여도
              </span>
            </div>
            <ComponentBreakdown
              components={risk?.components ?? {}}
              missing={risk?.missing_components ?? []}
            />
          </section>

          {/* 트랙 반응 패널 — gate 섹션이 오면 라이브 매트릭스, 없으면 정적 폴백 */}
          <TrackResponsePanel
            band={risk?.band ?? null}
            score={risk?.score ?? null}
            gate={latest?.gate ?? null}
          />

          {/* 차트 */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                시장 구조 차트
              </h2>
              <span className="text-sm text-slate-500">
                최근 {HISTORY_DAYS}일 · close 스냅샷 기준
                {latest?.structure?.trade_date
                  ? ` · 최신 ${latest.structure.trade_date} (${latest.structure.status})`
                  : ""}
              </span>
            </div>
            <div className="grid gap-2 lg:grid-cols-2">
              <ScoreHistoryChart points={points} />
              <ForeignFuturesChart points={points} />
              <BasisChart points={points} />
              <NightSignalTiles
                nightClose={
                  latest?.night_close ?? { available: false, status: "missing" }
                }
                latestPoint={latestPoint}
              />
            </div>
          </section>

          {/* 헤지 카드 (Phase 4B §6.1) — 권고 전용, 자동 주문 없음 */}
          <HedgeAdvisorCard
            data={hedge}
            history={hedgeHistory}
            isLoading={hedgeLoading}
          />
        </div>
      </div>
    </>
  );
}
