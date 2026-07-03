"use client";

import { AlertTriangle } from "lucide-react";
import type {
  PortfolioEquityLatest,
  PortfolioMddStages,
  PortfolioStage,
} from "@/lib/dashboard/portfolio";
import { PORTFOLIO_STAGES, normalizeStage } from "@/lib/dashboard/portfolio";
import { formatKstDateTime } from "@/lib/dashboard/format";

// 통합 자산 패널 (Phase 3D — roadmap §5.5). 일별 equity 배치의
// portfolio:equity:latest 발행을 표시 전용으로 렌더링한다. 서킷 브레이커는
// shadow 우선(미집행)이며, 이 패널은 어떤 단계/모드도 절대 변경하지 않는다.

function fmtKrw(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}

// 배치는 monthly_mdd_pct를 비율(fraction, -0.0494 = -4.94%)로 발행한다 —
// stages 임계(-0.05)와 동일 단위. 표시 시에만 %로 환산한다.
function fmtMddPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `${(v * 100).toFixed(2)}%`;
}

// 단계 배지 톤 (설계서 §7.1): NORMAL 정상 / REDUCE 신규 사이즈 50% /
// HALT_NEW 신규 진입 중단 / FULL_STOP 전 시스템 정지.
const STAGE_BADGE_CLASSES: Record<PortfolioStage, string> = {
  NORMAL:
    "border-emerald-300 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300",
  REDUCE:
    "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
  HALT_NEW:
    "border-orange-300 bg-orange-50 text-orange-700 dark:border-orange-800 dark:bg-orange-950/40 dark:text-orange-300",
  FULL_STOP:
    "border-rose-300 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300",
};

export function StageBadge({ stage }: { stage: string | null | undefined }) {
  const normalized = normalizeStage(stage);
  if (!normalized) {
    return (
      <span className="inline-flex items-center rounded border border-slate-300 bg-slate-50 px-2 py-0.5 text-[11px] font-bold text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
        단계 미산출
      </span>
    );
  }
  const spec = PORTFOLIO_STAGES.find((s) => s.stage === normalized);
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-bold ${STAGE_BADGE_CLASSES[normalized]}`}
    >
      {normalized}
      {spec ? ` — ${spec.description}` : ""}
    </span>
  );
}

// mode 배지 — TrackResponsePanel(GateModeBadge)의 shadow/enforce/off 관행 유지.
export function BreakerModeBadge({ mode }: { mode: string | null | undefined }) {
  const key = (mode ?? "").trim().toLowerCase();
  if (key === "enforce") {
    return (
      <span className="inline-flex items-center rounded border border-rose-300 bg-rose-50 px-2 py-0.5 text-[11px] font-bold text-rose-700 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300">
        enforce — 집행 중
      </span>
    );
  }
  if (key === "off") {
    return (
      <span className="inline-flex items-center rounded border border-slate-300 bg-slate-50 px-2 py-0.5 text-[11px] font-bold text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
        off — 비활성
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded border border-dashed border-amber-400 bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-700 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
      shadow — 미집행
    </span>
  );
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

function stageThresholdSub(stages: PortfolioMddStages | null): string {
  // config/portfolio.yaml 임계는 월초 대비 비율(-0.05 = -5%).
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  if (!stages) return "단계 임계 −5% / −8% / −12%";
  return `단계 임계 ${pct(stages.reduce.threshold)} / ${pct(
    stages.halt_new.threshold,
  )} / ${pct(stages.full_stop.threshold)}`;
}

export default function PortfolioEquityPanel({
  data,
  isLoading,
}: {
  data: PortfolioEquityLatest | undefined;
  isLoading: boolean;
}) {
  const equity = data?.equity ?? null;
  const stages = data?.stages ?? null;
  const unavailable = data !== undefined && data.status === "unavailable";
  // 라이브 mode(배치 발행)가 우선, 부재 시 config mode로 폴백.
  const mode = equity?.mode ?? stages?.mode ?? null;

  return (
    <section aria-label="통합 자산" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
            통합 자산
          </h2>
          {equity && <StageBadge stage={equity.stage} />}
          <BreakerModeBadge mode={mode} />
        </div>
        <span className="text-sm text-slate-500">
          {equity?.asof
            ? `${formatKstDateTime(equity.asof, "-")} KST`
            : "전체 계좌 + 트랙 A 원장 합산 · 일별 배치"}
        </span>
      </div>

      {unavailable && (
        <div
          role="status"
          className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
        >
          통합 자산 배치 미가동 — (
          <code className="text-xs">{data?.source}</code> 부재). 배치 가동 후
          총자산·트랙 분해·MDD 단계가 채워집니다.
        </div>
      )}

      {isLoading && !data ? (
        <div role="status" aria-label="Loading unified equity" className="sr-only">
          Loading unified equity
        </div>
      ) : null}

      {equity?.degraded && (
        <div
          role="alert"
          className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
        >
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div>
              <span className="font-bold">DEGRADED</span> — 일부 구성요소 결측
              {equity.missing_components.length > 0 && (
                <>: {equity.missing_components.join(", ")}</>
              )}
              <span className="ml-1">(합산치가 불완전할 수 있음)</span>
            </div>
          </div>
        </div>
      )}
      {equity && !equity.degraded && equity.stale && (
        <div
          role="alert"
          className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
        >
          마지막 발행이 오래되었습니다 ({formatKstDateTime(equity.asof, "-")}{" "}
          KST) — equity 배치 스케줄을 확인하세요.
        </div>
      )}

      {equity && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
          <Tile label="총자산" value={fmtKrw(equity.total_equity)} />
          <Tile
            label="트랙 B (주식)"
            value={fmtKrw(equity.track_b_equity)}
            sub="Tier 2 자동매매"
          />
          <Tile
            label="트랙 C (선물)"
            value={fmtKrw(equity.track_c_equity)}
            sub="Tier 2 자동매매"
          />
          <Tile
            label="트랙 A (코어)"
            value={
              equity.track_a_equity === null
                ? "미기록"
                : fmtKrw(equity.track_a_equity)
            }
            tone={
              equity.track_a_equity === null ? "text-slate-400" : undefined
            }
            sub="수동 원장"
          />
          <Tile
            label="월간 MDD"
            value={fmtMddPct(equity.monthly_mdd_pct)}
            tone={
              equity.monthly_mdd_pct !== null && equity.monthly_mdd_pct < 0
                ? "text-loss"
                : undefined
            }
            sub={stageThresholdSub(stages)}
          />
          <Tile
            label="월초 자산"
            value={fmtKrw(equity.month_start_equity)}
            sub={`월중 최고 ${fmtKrw(equity.month_peak_equity)}`}
          />
        </div>
      )}
    </section>
  );
}
