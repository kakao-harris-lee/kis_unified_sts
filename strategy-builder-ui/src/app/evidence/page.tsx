"use client";

import {
  AlertTriangle,
  ClipboardCheck,
  FileWarning,
  RefreshCcw,
} from "lucide-react";
import HeaderBar from "@/components/dashboard/HeaderBar";
import ErrorMessage from "@/components/dashboard/ErrorMessage";
import RefreshIndicator from "@/components/dashboard/RefreshIndicator";
import useQueryWithError from "@/hooks/dashboard/useQueryWithError";
import { useAssetClass } from "@/contexts/dashboard/AssetClassContext";
import { evidenceApi } from "@/lib/dashboard/api";
import type {
  EvidenceGap,
  EvidenceSummaryResponse,
  StrategyEvidenceSummary,
} from "@/lib/dashboard/evidence";
import { formatKstShort } from "@/lib/dashboard/format";
import { QUERY_INTERVALS_MS } from "@/lib/dashboard/queryIntervals";

function fmtNumber(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return v.toLocaleString("ko-KR");
}

function fmtKrw(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}

function deltaClass(v: number | null | undefined): string {
  if (v === null || v === undefined || v === 0) {
    return "text-slate-900 dark:text-slate-100";
  }
  return v > 0 ? "text-profit" : "text-loss";
}

function severityClass(severity: string): string {
  const normalized = severity.toLowerCase();
  if (normalized === "critical" || normalized === "error") {
    return "border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-200";
  }
  if (normalized === "warning") {
    return "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200";
  }
  return "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300";
}

function StatCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div className="mt-1 truncate text-lg font-bold text-slate-900 dark:text-slate-100">
        {value}
      </div>
    </div>
  );
}

function StrategyTable({ rows }: { rows: StrategyEvidenceSummary[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">Strategy evidence summary by selected asset class</caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["Strategy", "Accepted", "Rejected", "Paper P&L", "BT/Paper Δ", "Status"].map((h, i) => (
              <th
                key={h}
                scope="col"
                className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${i === 0 || i === 5 ? "text-left" : "text-right"}`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row) => (
            <tr key={row.strategy} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
              <td className="px-3 py-3 font-semibold text-slate-900 dark:text-slate-100">
                {row.strategy}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">
                {fmtNumber(row.accepted)}
              </td>
              <td className="px-3 py-3 text-right tabular-nums">
                {fmtNumber(row.rejected)}
              </td>
              <td className={`px-3 py-3 text-right tabular-nums font-semibold ${deltaClass(row.paperPnl)}`}>
                {fmtKrw(row.paperPnl)}
              </td>
              <td className={`px-3 py-3 text-right tabular-nums font-semibold ${deltaClass(row.backtestPaperDelta)}`}>
                {fmtKrw(row.backtestPaperDelta)}
              </td>
              <td className="px-3 py-3 text-left text-xs font-semibold uppercase tracking-normal text-slate-500">
                {row.status}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="px-3 py-8 text-center text-sm text-slate-500" colSpan={6}>
                No strategy evidence connected
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function EvidenceGapList({ gaps }: { gaps: EvidenceGap[] }) {
  if (gaps.length === 0) {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
        No evidence gaps reported.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {gaps.map((gap) => (
        <div
          key={gap.code}
          role={gap.severity.toLowerCase() === "warning" ? "alert" : "status"}
          className={`rounded-lg border p-3 text-sm ${severityClass(gap.severity)}`}
        >
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <div>
              <div className="font-semibold">{gap.code}</div>
              <div className="mt-1 text-xs">{gap.message}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function EvidencePage() {
  const { selectedAsset } = useAssetClass();
  const {
    data,
    isLoading,
    errorMessage,
    refetch,
    dataUpdatedAt,
    isFetching,
  } = useQueryWithError<EvidenceSummaryResponse>({
    queryKey: ["evidence-summary", selectedAsset],
    queryFn: () => evidenceApi.getSummary(selectedAsset).then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.slow,
  });

  const accepted = (data?.strategies ?? []).reduce((sum, row) => sum + row.accepted, 0);
  const rejected = (data?.strategies ?? []).reduce((sum, row) => sum + row.rejected, 0);
  const connected = (data?.strategies ?? []).length;

  return (
    <>
      <HeaderBar />
      <div className="mx-auto max-w-[1400px] px-2 pb-24 pt-2 sm:px-4 lg:px-6 lg:pb-2">
        <div className="space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <ClipboardCheck className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  Evidence Summary
                </h1>
                <p className="text-sm text-slate-500">
                  {data ? `${data.asset_class} · ${formatKstShort(data.generated_at)}` : selectedAsset}
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
                onClick={() => refetch()}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 focus-ring dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                aria-label="Refresh evidence summary"
              >
                <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          {errorMessage && (
            <ErrorMessage message={errorMessage} onRetry={() => refetch()} />
          )}

          {isLoading && !data ? (
            <div role="status" aria-label="Loading evidence summary" className="sr-only">
              Loading evidence summary
            </div>
          ) : null}

          <section className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            <StatCell label="Strategies Connected" value={`${connected}`} />
            <StatCell label="Accepted Decisions" value={`${accepted}`} />
            <StatCell label="Rejected Decisions" value={`${rejected}`} />
            <StatCell label="Evidence Gaps" value={`${(data?.evidence_gaps ?? []).length}`} />
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Strategy Evidence
              </h2>
              <span className="text-sm text-slate-500">
                {(data?.strategies ?? []).length} strategies
              </span>
            </div>
            <StrategyTable rows={data?.strategies ?? []} />
          </section>

          <section className="space-y-3">
            <div className="flex items-center gap-2">
              <FileWarning className="h-4 w-4 text-amber-500" aria-hidden="true" />
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Evidence Gaps
              </h2>
            </div>
            <EvidenceGapList gaps={data?.evidence_gaps ?? []} />
          </section>
        </div>
      </div>
    </>
  );
}
