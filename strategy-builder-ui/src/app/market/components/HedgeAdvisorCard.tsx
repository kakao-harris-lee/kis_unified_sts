"use client";

import { AlertTriangle, Shield } from "lucide-react";
import RiskBandBadge, {
  BAND_BADGE_CLASSES,
} from "@/components/dashboard/RiskBandBadge";
import { normalizeBand } from "@/lib/dashboard/marketRisk";
import type {
  PortfolioHedgeHistory,
  PortfolioHedgeLatest,
  PortfolioHedgeSnapshot,
} from "@/lib/dashboard/portfolio";
import { hedgeProductLabel } from "@/lib/dashboard/portfolio";
import { formatKstDateTime } from "@/lib/dashboard/format";
import Tile from "./Tile";

// 헤지 어드바이저 카드 (Phase 4B — roadmap §5.4/§6.1). portfolio:hedge:latest
// 발행(미니 KOSPI200 — O4)을 표시 전용으로 렌더링한다. 권고 전용 — 자동 주문
// 없음: 이 카드는 어떤 주문/집행 컨트롤도 절대 제공하지 않는다.

const HISTORY_DISPLAY_LIMIT = 10;

function fmtKrw(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}

function fmtBeta(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return v.toFixed(2);
}

// 선물 넷 계약수는 서명값(숏 음수) — 부호를 그대로 드러낸다.
function fmtSignedContracts(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  const rounded = Math.round(v);
  return `${rounded > 0 ? "+" : ""}${rounded.toLocaleString("ko-KR")}계약`;
}

function fmtPrice(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return v.toLocaleString("ko-KR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// 상시 라벨 — Phase 2 shadow 라벨 관행(amber dashed)과 동일 톤.
function AdvisoryOnlyLabel() {
  return (
    <span className="inline-flex items-center rounded border border-dashed border-amber-400 bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-700 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
      권고 전용 — 자동 주문 없음
    </span>
  );
}

// advisory_active면 밴드색 강조 배지, 아니면 muted "권고 없음".
function AdvisoryBadge({ hedge }: { hedge: PortfolioHedgeSnapshot | null }) {
  if (hedge?.advisory_active) {
    const band = normalizeBand(hedge.band);
    const tone = band
      ? BAND_BADGE_CLASSES[band]
      : "bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200";
    return (
      <span
        className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold ${tone}`}
      >
        헤지 검토 권고
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
      권고 없음
    </span>
  );
}

function Recommendation({ hedge }: { hedge: PortfolioHedgeSnapshot }) {
  const contracts = hedge.recommended_short_contracts;
  const active = hedge.advisory_active;
  const tone = active
    ? "border-orange-300 bg-orange-50 dark:border-orange-800 dark:bg-orange-950/30"
    : "border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/40";
  return (
    <div className={`rounded-lg border p-3 ${tone}`}>
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
        권고
      </div>
      <div className="mt-1 text-base font-bold text-slate-900 dark:text-slate-100">
        {contracts !== null && contracts > 0 ? (
          <>
            {hedgeProductLabel(hedge.product)} 숏 {contracts}계약 검토
            <span className="ml-2 text-xs font-medium text-slate-500 dark:text-slate-400">
              실행 시 잔여 노출 {fmtKrw(hedge.residual_exposure_after)}
            </span>
          </>
        ) : (
          "권고 계약수 없음"
        )}
      </div>
      {hedge.reason && (
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
          근거: {hedge.reason}
        </p>
      )}
    </div>
  );
}

function HistoryList({
  history,
}: {
  history: PortfolioHedgeHistory | undefined;
}) {
  const points = history?.points ?? [];
  // 최근 권고가 위로 오도록 역순 표시.
  const recent = points.slice(-HISTORY_DISPLAY_LIMIT).reverse();
  return (
    <div>
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          최근 권고 이력
        </h3>
        <span className="text-xs text-slate-500">
          최근 {history?.days ?? 30}일 · {points.length}건
        </span>
      </div>
      {recent.length === 0 ? (
        <div className="mt-2 rounded border border-slate-100 bg-slate-50 p-3 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-800/40">
          권고 이력 없음 — 어드바이저 가동 후 축적됩니다
        </div>
      ) : (
        <ul className="mt-2 divide-y divide-slate-100 dark:divide-slate-800">
          {recent.map((point) => (
            <li
              key={point.asof ?? point.trade_date ?? ""}
              className="flex items-center justify-between gap-2 py-1.5 text-sm"
            >
              <span className="tabular-nums text-slate-500">
                {point.trade_date ?? "-"}
              </span>
              <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                {point.recommended_short_contracts !== null &&
                point.recommended_short_contracts > 0
                  ? `숏 ${point.recommended_short_contracts}계약`
                  : "권고 없음"}
              </span>
              <RiskBandBadge band={point.band} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function HedgeAdvisorCard({
  data,
  history,
  isLoading,
}: {
  data: PortfolioHedgeLatest | undefined;
  history: PortfolioHedgeHistory | undefined;
  isLoading: boolean;
}) {
  const hedge = data?.hedge ?? null;
  const unavailable = data !== undefined && data.status === "unavailable";

  return (
    <section
      aria-label="Hedge advisor"
      className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Shield className="h-4 w-4 text-slate-500" aria-hidden="true" />
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            헤지 어드바이저
          </h2>
          <AdvisoryBadge hedge={hedge} />
        </div>
        <AdvisoryOnlyLabel />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        현물 β-노출 vs 선물 넷 노출 → 미니 KOSPI200 헤지 계약수 권고 (§5.4).
        집행은 항상 수동 — 이 카드는 어떤 주문도 내지 않습니다.
      </p>

      {isLoading && !data ? (
        <div
          role="status"
          aria-label="Loading hedge advisor"
          className="sr-only"
        >
          Loading hedge advisor
        </div>
      ) : null}

      {unavailable && (
        <div
          role="status"
          className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          헤지 어드바이저 미가동 — (
          <code className="text-xs">{data?.source}</code> 부재). 엔진 가동 후
          β-노출·권고 계약수가 채워집니다.
        </div>
      )}

      {hedge?.degraded && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
        >
          <div className="flex items-start gap-2">
            <AlertTriangle
              className="mt-0.5 h-4 w-4 shrink-0"
              aria-hidden="true"
            />
            <div>
              <span className="font-bold">DEGRADED</span> — 일부 입력 결측
              {hedge.missing_components.length > 0 && (
                <>: {hedge.missing_components.join(", ")}</>
              )}
              <span className="ml-1">(권고 수치가 불완전할 수 있음)</span>
            </div>
          </div>
        </div>
      )}
      {hedge && !hedge.degraded && hedge.stale && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
        >
          마지막 권고 산출이 오래되었습니다 (
          {formatKstDateTime(hedge.asof, "-")} KST) — 어드바이저 스케줄을
          확인하세요.
        </div>
      )}

      {hedge && (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
            <Tile
              label="현물 롱 명목가"
              value={fmtKrw(hedge.stock_long_notional)}
              sub={`포트폴리오 β ${fmtBeta(hedge.portfolio_beta)} → β-노출 ${fmtKrw(hedge.beta_notional)}`}
            />
            <Tile
              label="선물 넷 노출"
              value={fmtSignedContracts(hedge.futures_net_contracts)}
              sub={`${fmtKrw(hedge.futures_net_notional)} (서명 · 숏 음수)`}
            />
            <Tile
              label="순 β-노출"
              value={fmtKrw(hedge.net_beta_exposure)}
              sub="현물 β-노출 + 선물 넷 노출"
            />
          </div>

          <Recommendation hedge={hedge} />

          <p className="text-[11px] text-slate-400">
            {hedgeProductLabel(hedge.product)} · 승수{" "}
            {fmtKrw(hedge.multiplier)}/pt · 선물가{" "}
            {fmtPrice(hedge.futures_price)} · 밴드 {hedge.band ?? "-"} · score{" "}
            {hedge.score !== null ? hedge.score.toFixed(1) : "-"} ·{" "}
            {formatKstDateTime(hedge.asof, "-")} KST
          </p>
        </div>
      )}

      <div className="mt-4">
        <HistoryList history={history} />
      </div>
    </section>
  );
}
