"use client";

import type { RiskBand } from "@/lib/dashboard/marketRisk";
import { RISK_BANDS, normalizeBand } from "@/lib/dashboard/marketRisk";
import RiskBandBadge from "@/components/dashboard/RiskBandBadge";

// §4.2 반응 매트릭스 (roadmap 정본의 정적 렌더). Phase 2 enforcement 전까지
// 어떤 트랙에도 집행되지 않는다 — "shadow — 미집행" 라벨을 상시 표시한다.
interface TrackDirectives {
  trackB: string;
  trackC: string;
  trackA: string;
}

const TRACK_MATRIX: Record<RiskBand, TrackDirectives> = {
  LOW: {
    trackB: "매수 신호 정상 실행",
    trackC: "롱/숏 양방향 · 정상 사이즈",
    trackA: "정상 보유",
  },
  NEUTRAL: {
    trackB: "정상 실행",
    trackC: "롱/숏 양방향 · 정상 사이즈",
    trackA: "정상 보유",
  },
  ELEVATED: {
    trackB: "신뢰도 HIGH 신호만 실행",
    trackC: "양방향 · 사이즈 70%",
    trackA: "정상 보유",
  },
  HIGH: {
    trackB: "신규 롱 전면 금지 · 보유분 손절/청산 규칙만 가동",
    trackC: "신규 롱 금지 · 숏 편향 허용 · 사이즈 50% · 보유 현물 헤지 검토",
    trackA: "신규 매수 중단",
  },
  CRITICAL: {
    trackB: "신규 진입 전면 금지",
    trackC: "신규 진입 금지(청산·헤지 목적 숏만) · 헤지 실행 검토",
    trackA: "신규 매수 중단 · Tier 3 발동 감시 (KOSPI 고점 대비 −15% 워치)",
  },
};

const TRACK_ROWS: { key: keyof TrackDirectives; label: string; desc: string }[] =
  [
    { key: "trackB", label: "트랙 B", desc: "주식 파이프라인" },
    { key: "trackC", label: "트랙 C", desc: "선물" },
    { key: "trackA", label: "트랙 A", desc: "중장기 코어 (수동)" },
  ];

export default function TrackResponsePanel({
  band,
  score,
}: {
  band: string | null;
  score: number | null;
}) {
  const activeBand = normalizeBand(band);
  const directives = activeBand ? TRACK_MATRIX[activeBand] : null;
  const bandSpec = activeBand
    ? RISK_BANDS.find((spec) => spec.band === activeBand)
    : null;

  return (
    <section
      aria-label="Track response matrix"
      className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            트랙 반응 매트릭스
          </h2>
          {activeBand && <RiskBandBadge band={activeBand} />}
        </div>
        <span className="inline-flex items-center rounded border border-dashed border-amber-400 bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-700 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
          shadow — 미집행
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {activeBand && bandSpec
          ? `현재 밴드 ${bandSpec.label}${
              score !== null ? ` · score ${score.toFixed(1)}` : ""
            } 기준 지시입니다. Phase 2 enforcement 전까지 로그 전용(shadow)이며 어떤 주문도 차단/변경하지 않습니다.`
          : "밴드가 산출되면 트랙별 지시가 표시됩니다. 현재는 표시할 밴드가 없습니다."}
      </p>
      {directives ? (
        <ul className="mt-3 space-y-2">
          {TRACK_ROWS.map((row) => (
            <li
              key={row.key}
              className="flex flex-col gap-1 rounded border border-slate-100 bg-slate-50 p-2.5 sm:flex-row sm:items-center sm:gap-3 dark:border-slate-800 dark:bg-slate-800/40"
            >
              <div className="w-40 shrink-0">
                <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {row.label}
                </span>
                <span className="ml-1.5 text-xs text-slate-500">{row.desc}</span>
              </div>
              <span className="text-sm text-slate-700 dark:text-slate-200">
                {directives[row.key]}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-3 rounded border border-slate-100 bg-slate-50 p-4 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-800/40">
          밴드 미산출 — 매트릭스 대기 중
        </div>
      )}
    </section>
  );
}
