"use client";

import type { MarketRiskComponent } from "@/lib/dashboard/marketRisk";
import { formatKstShort } from "@/lib/dashboard/format";

// Fixed 8-component contract order + operator-facing labels.
const COMPONENT_LABELS: Record<string, string> = {
  foreign_fut: "외국인 선물 수급",
  basis: "베이시스",
  usdkrw: "USD/KRW",
  program: "프로그램 매매",
  oi: "미결제약정",
  overseas: "해외 지수 선물",
  vol: "변동성 (HAR-RV)",
  trend: "지수 추세",
};

function fmtNum(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined ? "-" : v.toFixed(digits);
}

function fmtRaw(raw: unknown): string {
  if (raw === null || raw === undefined || raw === "") return "-";
  if (typeof raw === "number") {
    return Math.abs(raw) >= 1000
      ? Math.round(raw).toLocaleString("ko-KR")
      : raw.toLocaleString("ko-KR", { maximumFractionDigits: 3 });
  }
  return String(raw);
}

function SubScoreBar({ sub }: { sub: number | null }) {
  if (sub === null) {
    return <span className="text-xs text-slate-400">-</span>;
  }
  const clamped = Math.max(0, Math.min(100, sub));
  return (
    <div className="flex items-center gap-2">
      <div
        aria-hidden="true"
        className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800"
      >
        <div
          className={`h-full rounded-full ${
            clamped >= 70
              ? "bg-rose-500"
              : clamped >= 55
                ? "bg-amber-500"
                : "bg-slate-400"
          }`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="tabular-nums font-semibold text-slate-900 dark:text-slate-100">
        {clamped.toFixed(0)}
      </span>
    </div>
  );
}

export default function ComponentBreakdown({
  components,
  missing,
}: {
  components: Record<string, MarketRiskComponent>;
  missing: string[];
}) {
  const rows = Object.entries(components);
  const missingSet = new Set(missing);

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">
          Market risk score component breakdown: sub-score, weight,
          contribution, raw value, and freshness per component
        </caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["구성요소", "Sub-score", "가중치", "기여도", "원값", "신선도"].map(
              (h, i) => (
                <th
                  key={h}
                  scope="col"
                  className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${
                    i === 0 ? "text-left" : i === 1 ? "text-left" : "text-right"
                  }`}
                >
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map(([name, component]) => {
            const isMissing = missingSet.has(name) || component.sub === null;
            return (
              <tr
                key={name}
                className={`hover:bg-slate-50 dark:hover:bg-slate-800/50 ${
                  isMissing ? "opacity-70" : ""
                }`}
              >
                <td className="px-3 py-2.5">
                  <div className="font-medium text-slate-900 dark:text-slate-100">
                    {COMPONENT_LABELS[name] ?? name}
                  </div>
                  <div className="text-[11px] text-slate-400">{name}</div>
                </td>
                <td className="px-3 py-2.5">
                  {isMissing ? (
                    <span className="inline-flex items-center rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium uppercase text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                      missing
                    </span>
                  ) : (
                    <SubScoreBar sub={component.sub} />
                  )}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-300">
                  {fmtNum(component.weight, 0)}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums font-semibold text-slate-900 dark:text-slate-100">
                  {fmtNum(component.contribution)}
                </td>
                <td className="px-3 py-2.5 text-right tabular-nums text-slate-600 dark:text-slate-300">
                  {fmtRaw(component.raw)}
                </td>
                <td className="px-3 py-2.5 text-right text-xs text-slate-500">
                  {component.asof ? formatKstShort(component.asof) : "-"}
                </td>
              </tr>
            );
          })}
          {rows.length === 0 && (
            <tr>
              <td
                className="px-3 py-8 text-center text-sm text-slate-500"
                colSpan={6}
              >
                No component breakdown published yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
