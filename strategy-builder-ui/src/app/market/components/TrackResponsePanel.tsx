"use client";

import type {
  MarketRiskGateInfo,
  MarketRiskGateRule,
  RiskBand,
} from "@/lib/dashboard/marketRisk";
import { RISK_BANDS, normalizeBand } from "@/lib/dashboard/marketRisk";
import RiskBandBadge from "@/components/dashboard/RiskBandBadge";

// §4.2 반응 매트릭스. gate 섹션(config/market_risk_gate.yaml 라이브)이 있으면
// 트랙 B/C는 라이브 매트릭스로 렌더링하고, 없으면 roadmap 정본의 정적
// 매트릭스로 폴백한다. 트랙 A(중장기 코어)는 수동 운용 지시라 항상 정적이다.
// 표시 전용 — 이 패널은 게이트 mode를 절대 변경하지 않는다.
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

// 라이브 매트릭스 컬럼: gate.matrix의 asset 키 ↔ 트랙 매핑 (§5.1/§5.2).
const LIVE_COLUMNS: { asset: string; label: string }[] = [
  { asset: "stock", label: "트랙 B · 주식" },
  { asset: "futures", label: "트랙 C · 선물" },
];

function ruleDirective(rule: MarketRiskGateRule | undefined): string {
  if (!rule) {
    return "규칙 미정의 — fail-open 통과";
  }
  const parts: string[] = [];
  if (!rule.allow_long && !rule.allow_short) {
    parts.push("신규 진입 전면 금지");
  } else if (!rule.allow_long) {
    parts.push("신규 롱 금지");
  } else if (!rule.allow_short) {
    parts.push("신규 숏 금지");
  }
  if (rule.min_confidence) {
    parts.push(`신뢰도 ${rule.min_confidence} 이상만`);
  }
  if (rule.size_factor < 1) {
    parts.push(`사이즈 ${Math.round(rule.size_factor * 100)}%`);
  }
  return parts.length > 0 ? parts.join(" · ") : "정상 실행";
}

function normalizeGateMode(mode: string | null | undefined): string {
  return (mode ?? "").trim().toLowerCase();
}

function GateModeBadge({ mode }: { mode: string | null | undefined }) {
  const key = normalizeGateMode(mode);
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

function liveModeDescription(mode: string): string {
  if (mode === "enforce") {
    return "config/market_risk_gate.yaml 라이브 매트릭스 — 차단 규칙이 신규 진입에 실제 집행됩니다.";
  }
  if (mode === "off") {
    return "게이트 비활성(off) — 매트릭스는 참고용으로만 표시되며 집행되지 않습니다.";
  }
  return "config/market_risk_gate.yaml 라이브 매트릭스 — shadow 모드는 로그 전용이며 어떤 주문도 차단/변경하지 않습니다.";
}

function LiveMatrixTable({
  gate,
  activeBand,
}: {
  gate: MarketRiskGateInfo;
  activeBand: RiskBand | null;
}) {
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full min-w-[560px] text-sm">
        <caption className="sr-only">밴드별 트랙 반응 매트릭스 (라이브)</caption>
        <thead>
          <tr className="text-left text-[11px] font-medium uppercase text-slate-500">
            <th scope="col" className="px-2 py-1.5">
              Band
            </th>
            {LIVE_COLUMNS.map((column) => (
              <th scope="col" key={column.asset} className="px-2 py-1.5">
                {column.label}
              </th>
            ))}
            <th scope="col" className="px-2 py-1.5">
              트랙 A · 코어 (수동)
            </th>
          </tr>
        </thead>
        <tbody>
          {RISK_BANDS.map((spec) => {
            const isActive = spec.band === activeBand;
            const rowTone = isActive
              ? "bg-slate-100 dark:bg-slate-800/60"
              : "";
            return (
              <tr
                key={spec.band}
                aria-current={isActive ? "true" : undefined}
                className={`border-t border-slate-100 dark:border-slate-800 ${rowTone}`}
              >
                <td className="whitespace-nowrap px-2 py-2">
                  <div className="flex items-center gap-1.5">
                    <RiskBandBadge band={spec.band} />
                    {isActive && (
                      <span className="rounded bg-slate-900 px-1.5 py-0.5 text-[10px] font-bold text-white dark:bg-slate-100 dark:text-slate-900">
                        현재
                      </span>
                    )}
                  </div>
                </td>
                {LIVE_COLUMNS.map((column) => (
                  <td
                    key={column.asset}
                    className={`px-2 py-2 ${
                      isActive
                        ? "font-semibold text-slate-900 dark:text-slate-100"
                        : "text-slate-600 dark:text-slate-300"
                    }`}
                  >
                    {ruleDirective(gate.matrix[column.asset]?.[spec.band])}
                  </td>
                ))}
                <td
                  className={`px-2 py-2 ${
                    isActive
                      ? "font-semibold text-slate-900 dark:text-slate-100"
                      : "text-slate-500 dark:text-slate-400"
                  }`}
                >
                  {TRACK_MATRIX[spec.band].trackA}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-slate-400">
        트랙 B/C는 config/market_risk_gate.yaml 라이브 규칙, 트랙 A는 roadmap
        §4.2 수동 운용 지시입니다.
      </p>
    </div>
  );
}

export default function TrackResponsePanel({
  band,
  score,
  gate = null,
}: {
  band: string | null;
  score: number | null;
  gate?: MarketRiskGateInfo | null;
}) {
  const activeBand = normalizeBand(band);
  const directives = activeBand ? TRACK_MATRIX[activeBand] : null;
  const bandSpec = activeBand
    ? RISK_BANDS.find((spec) => spec.band === activeBand)
    : null;
  const liveGate =
    gate && gate.matrix && Object.keys(gate.matrix).length > 0 ? gate : null;
  const liveMode = normalizeGateMode(liveGate?.mode);

  const scoreSuffix = score !== null ? ` · score ${score.toFixed(1)}` : "";
  const bandLine =
    activeBand && bandSpec
      ? `현재 밴드 ${bandSpec.label}${scoreSuffix} 기준 지시입니다.`
      : "밴드가 산출되면 트랙별 지시가 표시됩니다. 현재는 표시할 밴드가 없습니다.";

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
        <GateModeBadge mode={liveGate ? liveGate.mode : "shadow"} />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        {liveGate
          ? `${bandLine} ${liveModeDescription(liveMode)}`
          : activeBand && bandSpec
            ? `${bandLine} Phase 2 enforcement 전까지 로그 전용(shadow)이며 어떤 주문도 차단/변경하지 않습니다.`
            : bandLine}
      </p>
      {liveGate ? (
        <LiveMatrixTable gate={liveGate} activeBand={activeBand} />
      ) : directives ? (
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
