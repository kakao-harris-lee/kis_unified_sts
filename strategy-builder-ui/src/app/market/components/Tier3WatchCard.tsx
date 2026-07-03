"use client";

import { TrendingDown } from "lucide-react";
import type { PortfolioCoreLatest, Tier3WatchSnapshot } from "@/lib/dashboard/portfolio";
import { formatKstDateTime } from "@/lib/dashboard/format";
import ManualTrackLabel from "./ManualTrackLabel";
import Tile from "./Tile";

// Tier 3 워치 카드 (Phase 5E — roadmap §5.3/§6.1). portfolio:tier3:watch
// 발행(KOSPI 고점 대비 드로다운, −15% 트리거)을 표시 전용으로 렌더링한다.
// 수동 트랙 — 발동 판단·분할 매수 집행은 항상 수동이며, 이 카드는 어떤 매매
// 컨트롤도 제공하지 않는다. drawdown/trigger_threshold는 fraction(−0.16 =
// −16%) — 표시할 때만 ×100 변환한다.

// 게이지 표시 스케일: 0 ~ −25% (트리거 −15%가 60% 지점에 오도록).
const GAUGE_SCALE_FRACTION = 0.25;
// 축 눈금 (fraction, 5%p 간격 — justify-between 균등 배치 전제).
const GAUGE_TICKS = [0, -0.05, -0.1, -0.15, -0.2, -0.25];

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "-";
  return `${(v * 100).toFixed(digits)}%`;
}

function fmtIndex(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return v.toLocaleString("ko-KR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// fraction(≤0)을 0~100% 게이지 좌표로 변환 (0=왼쪽, −25%=오른쪽 끝).
function gaugePosition(fraction: number): number {
  const magnitude = Math.min(Math.max(-fraction, 0), GAUGE_SCALE_FRACTION);
  return (magnitude / GAUGE_SCALE_FRACTION) * 100;
}

// triggered면 rose 강조 배지, 아니면 muted "미발동" — 상태는 항상 라벨로도
// 전달한다 (색상 단독 의미 전달 금지).
function TriggerBadge({ tier3 }: { tier3: Tier3WatchSnapshot | null }) {
  if (tier3?.triggered) {
    return (
      <span className="inline-flex items-center rounded bg-rose-100 px-2 py-0.5 text-xs font-bold text-rose-800 dark:bg-rose-900/40 dark:text-rose-200">
        Tier 3 발동 감시 — 분할 매수 검토는 수동
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
      미발동
    </span>
  );
}

function DrawdownGauge({ tier3 }: { tier3: Tier3WatchSnapshot }) {
  const drawdown = tier3.drawdown;
  const threshold = tier3.trigger_threshold;
  const fillPct = drawdown === null ? null : gaugePosition(drawdown);
  const thresholdPct = threshold === null ? null : gaugePosition(threshold);
  const fillTone = tier3.triggered ? "bg-rose-500" : "bg-slate-400";

  return (
    <div
      role="img"
      aria-label={
        drawdown === null
          ? "KOSPI drawdown unavailable"
          : `KOSPI 고점 대비 드로다운 ${fmtPct(drawdown)}, 트리거 ${fmtPct(threshold)}${
              tier3.triggered ? " — 발동" : " — 미발동"
            }`
      }
      className="w-full"
    >
      <div className="relative">
        <div className="h-3 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
          {fillPct !== null && (
            <div
              className={`h-full rounded-full ${fillTone}`}
              style={{ width: `${fillPct}%` }}
            />
          )}
        </div>
        {/* 현재 드로다운 니들 */}
        {fillPct !== null && (
          <div
            aria-hidden="true"
            className="absolute -top-1 h-5 w-0.5 -translate-x-1/2 rounded bg-slate-900 dark:bg-slate-100"
            style={{ left: `${fillPct}%` }}
          />
        )}
        {/* −15% 트리거 라인 */}
        {thresholdPct !== null && (
          <div
            aria-hidden="true"
            className="absolute -top-1 h-5 w-0.5 -translate-x-1/2 rounded bg-rose-600 dark:bg-rose-400"
            style={{ left: `${thresholdPct}%` }}
          />
        )}
      </div>
      <div className="mt-1 flex justify-between text-[10px] tabular-nums text-slate-400">
        {GAUGE_TICKS.map((tick) => (
          <span
            key={tick}
            className={
              threshold !== null && tick === threshold
                ? "font-semibold text-rose-600 dark:text-rose-400"
                : undefined
            }
          >
            {fmtPct(tick, 0)}
          </span>
        ))}
      </div>
      <div className="mt-1 text-[11px] text-rose-600 dark:text-rose-400">
        ▎트리거 {fmtPct(threshold)} — 고점 대비 드로다운이 임계에 도달하면
        Tier 3 발동 감시
      </div>
    </div>
  );
}

export default function Tier3WatchCard({
  data,
  isLoading,
}: {
  data: PortfolioCoreLatest | undefined;
  isLoading: boolean;
}) {
  const tier3 = data?.tier3 ?? null;
  const unavailable = data !== undefined && tier3 === null;

  return (
    <section
      aria-label="Tier 3 watch"
      className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <TrendingDown className="h-4 w-4 text-slate-500" aria-hidden="true" />
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Tier 3 워치
          </h2>
          <TriggerBadge tier3={tier3} />
        </div>
        <ManualTrackLabel />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        KOSPI 고점 대비 드로다운 워치 — −15% 트리거 (§5.3/§6.1). 발동 판단과
        분할 매수 집행은 항상 수동이며, 자동 매수는 없습니다.
      </p>

      {isLoading && !data ? (
        <div role="status" aria-label="Loading tier 3 watch" className="sr-only">
          Loading tier 3 watch
        </div>
      ) : null}

      {unavailable && (
        <div
          role="status"
          className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          Tier 3 워치 미가동 — (<code className="text-xs">{data?.source}</code>{" "}
          부재). 워치 가동 후 드로다운 게이지가 채워집니다.
        </div>
      )}

      {tier3 && tier3.stale && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
        >
          마지막 워치 산출이 오래되었습니다 (
          {formatKstDateTime(tier3.asof, "-")} KST) — 워치 스케줄을 확인하세요.
        </div>
      )}

      {tier3 && (
        <div className="mt-3 space-y-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
            <div className="shrink-0">
              <div className="text-xs font-medium uppercase text-slate-500">
                드로다운
              </div>
              <div
                className={`text-3xl font-bold tabular-nums ${
                  tier3.triggered
                    ? "text-rose-600 dark:text-rose-400"
                    : "text-slate-900 dark:text-slate-100"
                }`}
              >
                {fmtPct(tier3.drawdown)}
              </div>
            </div>
            <div className="min-w-0 flex-1">
              <DrawdownGauge tier3={tier3} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Tile label="KOSPI 종가" value={fmtIndex(tier3.kospi_close)} />
            <Tile
              label="KOSPI 고점"
              value={fmtIndex(tier3.kospi_peak)}
              sub="워치 기준 피크"
            />
          </div>

          <p className="text-[11px] text-slate-400">
            트리거 {fmtPct(tier3.trigger_threshold)} ·{" "}
            {formatKstDateTime(tier3.asof, "-")} KST
          </p>
        </div>
      )}
    </section>
  );
}
