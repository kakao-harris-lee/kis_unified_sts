"use client";

import { Briefcase } from "lucide-react";
import type {
  CoreCandidate,
  CoreHolding,
  CoreRebalancing,
  CoreSectorSpec,
  PortfolioCoreLatest,
} from "@/lib/dashboard/portfolio";
import ManualTrackLabel from "./ManualTrackLabel";

// 코어 홀딩스 카드 (Phase 5E — roadmap §5.3). config/portfolio/core_holdings.yaml
// (Phase 5A 로더)의 보유/후보 종목·Kill Criteria·섹터 배분을 표시 전용으로
// 렌더링한다. 수동 트랙 — 자동 매매 없음: 이 카드는 어떤 매매/원장 수정
// 컨트롤도 절대 제공하지 않는다. weight/target/actual/drift는 전부 fraction —
// 표시할 때만 ×100 변환한다.

// 로더 계약 기본값 미러 (rebalancing 부재 시 표시용 폴백).
const DEFAULT_DRIFT_THRESHOLD = 0.1;

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "-";
  return `${(v * 100).toFixed(digits)}%`;
}

function fmtSignedPctPoint(v: number): string {
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%p`;
}

function fmtKrw(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}

// Kill Criteria — 무효화 조건 expandable (§5.3: 논거 1문장 + 무효화 조건).
function KillCriteria({ criteria }: { criteria: string[] }) {
  if (criteria.length === 0) {
    return <span className="text-xs text-slate-400">-</span>;
  }
  return (
    <details className="group">
      <summary className="focus-ring cursor-pointer select-none rounded text-xs font-medium text-slate-600 underline decoration-dotted underline-offset-2 dark:text-slate-300">
        {criteria.length}개 보기
      </summary>
      <ul className="mt-1.5 list-disc space-y-1 pl-4 text-xs text-slate-600 dark:text-slate-300">
        {criteria.map((criterion) => (
          <li key={criterion}>{criterion}</li>
        ))}
      </ul>
    </details>
  );
}

// 섹터 배분 바 — 실비중(채움) vs 목표(마커 틱). drift ±10%p(설정값) 초과 시
// amber 채움 + "드리프트" 라벨 병기 (색상 단독 의미 전달 금지).
function SectorAllocationRow({
  spec,
  driftThreshold,
}: {
  spec: CoreSectorSpec;
  driftThreshold: number;
}) {
  const actual = spec.actual_weight;
  const target = spec.target_weight;
  const drift = actual !== null && target !== null ? actual - target : null;
  const drifted = drift !== null && Math.abs(drift) > driftThreshold;
  const fillPct =
    actual === null ? null : Math.max(0, Math.min(100, actual * 100));
  const targetPct =
    target === null ? null : Math.max(0, Math.min(100, target * 100));

  return (
    <li className="py-1.5">
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="font-medium text-slate-900 dark:text-slate-100">
          {spec.label}
        </span>
        <span className="flex items-center gap-2">
          {drifted && (
            <span className="inline-flex items-center rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-bold text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
              드리프트 {fmtSignedPctPoint(drift)}
            </span>
          )}
          <span className="tabular-nums text-xs text-slate-500">
            {actual === null ? "실비중 미산출" : `실 ${fmtPct(actual)}`} · 목표{" "}
            {fmtPct(target)}
          </span>
        </span>
      </div>
      <div
        aria-hidden="true"
        className="relative mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
      >
        {fillPct !== null && (
          <div
            className={`h-full rounded-full ${
              drifted ? "bg-amber-500" : "bg-slate-400"
            }`}
            style={{ width: `${fillPct}%` }}
          />
        )}
        {targetPct !== null && (
          <div
            className="absolute top-0 h-full w-0.5 -translate-x-1/2 bg-slate-700 dark:bg-slate-200"
            style={{ left: `${targetPct}%` }}
          />
        )}
      </div>
    </li>
  );
}

function HoldingsTable({
  holdings,
  rebalancing,
}: {
  holdings: CoreHolding[];
  rebalancing: CoreRebalancing | null;
}) {
  const singleMax = rebalancing?.single_holding_max ?? null;
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">
          Track A core holdings: name, sector, thesis, valuation, weight, and
          kill criteria per holding
        </caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["종목", "섹터", "논거", "평가액", "비중", "Kill Criteria"].map(
              (h, i) => (
                <th
                  key={h}
                  scope="col"
                  className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${
                    i === 3 || i === 4 ? "text-right" : "text-left"
                  }`}
                >
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {holdings.map((holding) => {
            const overCap =
              singleMax !== null &&
              holding.weight !== null &&
              holding.weight > singleMax;
            return (
              <tr
                key={holding.symbol ?? holding.name ?? ""}
                className="align-top hover:bg-slate-50 dark:hover:bg-slate-800/50"
              >
                <td className="px-3 py-2.5">
                  <div className="font-medium text-slate-900 dark:text-slate-100">
                    {holding.name ?? holding.symbol ?? "-"}
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {holding.symbol ?? "-"}
                  </div>
                </td>
                <td className="px-3 py-2.5 text-slate-600 dark:text-slate-300">
                  {holding.sector_label ?? holding.sector ?? "-"}
                </td>
                <td className="max-w-[18rem] px-3 py-2.5 text-slate-600 dark:text-slate-300">
                  {holding.thesis ?? "-"}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums text-slate-900 dark:text-slate-100">
                  {fmtKrw(holding.valuation)}
                  <div className="text-[11px] font-normal text-slate-400">
                    {holding.last_valuation?.date
                      ? `${holding.last_valuation.date} 평가`
                      : "평단 기준"}
                  </div>
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums">
                  <span
                    className={
                      overCap
                        ? "font-semibold text-amber-700 dark:text-amber-300"
                        : "text-slate-600 dark:text-slate-300"
                    }
                  >
                    {fmtPct(holding.weight)}
                  </span>
                  {overCap && (
                    <div className="text-[11px] text-amber-700 dark:text-amber-300">
                      단일 종목 상한 {fmtPct(singleMax, 0)} 초과
                    </div>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  <KillCriteria criteria={holding.kill_criteria} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CandidateList({ candidates }: { candidates: CoreCandidate[] }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        후보 리스트
      </h3>
      {candidates.length === 0 ? (
        <div className="mt-2 rounded border border-slate-100 bg-slate-50 p-3 text-center text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-800/40">
          후보 없음
        </div>
      ) : (
        <ul className="mt-2 divide-y divide-slate-100 dark:divide-slate-800">
          {candidates.map((candidate) => (
            <li
              key={candidate.symbol ?? candidate.name ?? ""}
              className="py-2 text-sm"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-slate-900 dark:text-slate-100">
                  {candidate.name ?? candidate.symbol ?? "-"}
                </span>
                <span className="text-[11px] text-slate-400">
                  {candidate.symbol ?? "-"} ·{" "}
                  {candidate.sector_label ?? candidate.sector ?? "-"}
                </span>
              </div>
              {candidate.thesis && (
                <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-300">
                  {candidate.thesis}
                </p>
              )}
              <div className="mt-1">
                <KillCriteria criteria={candidate.kill_criteria} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function CoreHoldingsCard({
  data,
  isLoading,
}: {
  data: PortfolioCoreLatest | undefined;
  isLoading: boolean;
}) {
  const holdings = data?.holdings ?? [];
  const candidates = data?.candidates ?? [];
  const sectors = data?.sectors ?? null;
  const rebalancing = data?.rebalancing ?? null;
  const driftThreshold =
    rebalancing?.drift_threshold_pct ?? DEFAULT_DRIFT_THRESHOLD;
  const sectorEntries = sectors ? Object.entries(sectors) : [];

  return (
    <section
      aria-label="Core holdings"
      className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Briefcase className="h-4 w-4 text-slate-500" aria-hidden="true" />
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            코어 홀딩스 — 트랙 A
          </h2>
        </div>
        <ManualTrackLabel />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        중장기 코어 보유 — 투자 논거 1문장 + Kill Criteria 기반 수동 운용
        (§5.3). 이 카드는 어떤 매매 컨트롤도 제공하지 않습니다.
      </p>

      {isLoading && !data ? (
        <div
          role="status"
          aria-label="Loading core holdings"
          className="sr-only"
        >
          Loading core holdings
        </div>
      ) : null}

      {sectorEntries.length > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              섹터 배분 — 실비중 vs 목표
            </h3>
            <span className="text-xs text-slate-500">
              드리프트 임계 ±{fmtPct(driftThreshold, 0)}p
            </span>
          </div>
          <ul className="mt-1">
            {sectorEntries.map(([key, spec]) => (
              <SectorAllocationRow
                key={key}
                spec={spec}
                driftThreshold={driftThreshold}
              />
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            보유 종목
          </h3>
          <span className="text-xs text-slate-500">{holdings.length}종목</span>
        </div>
        {holdings.length === 0 ? (
          <div
            role="status"
            className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
          >
            보유 종목 미등록 —{" "}
            <code className="text-xs">config/portfolio/core_holdings.yaml</code>{" "}
            또는 <code className="text-xs">sts portfolio</code>로 등록하세요.
          </div>
        ) : (
          <div className="mt-2">
            <HoldingsTable holdings={holdings} rebalancing={rebalancing} />
          </div>
        )}
      </div>

      <div className="mt-4">
        <CandidateList candidates={candidates} />
      </div>
    </section>
  );
}
