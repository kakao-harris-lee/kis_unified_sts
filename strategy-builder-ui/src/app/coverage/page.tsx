"use client";

import {
  AlertTriangle,
  CheckCircle2,
  DatabaseZap,
  RefreshCcw,
  XCircle,
} from "lucide-react";
import HeaderBar from "@/components/dashboard/HeaderBar";
import ErrorMessage from "@/components/dashboard/ErrorMessage";
import RefreshIndicator from "@/components/dashboard/RefreshIndicator";
import useQueryWithError from "@/hooks/dashboard/useQueryWithError";
import { useAssetClass } from "@/contexts/dashboard/AssetClassContext";
import { coverageApi } from "@/lib/dashboard/api";
import type {
  CoverageResponse,
  CoverageSource,
  ExperimentCoverageRow,
} from "@/lib/dashboard/coverage";

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

function sourceLabel(name: string): string {
  const labels: Record<string, string> = {
    screener_universe: "Screener Universe",
    trade_targets: "Trade Targets",
    daily_indicators: "Daily Indicators",
    futures_data_coverage: "Futures Coverage",
  };
  return labels[name] ?? name;
}

function StatusBadge({ ok }: { ok: boolean }) {
  const Icon = ok ? CheckCircle2 : XCircle;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold ${
        ok
          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
          : "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300"
      }`}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {ok ? "available" : "missing"}
    </span>
  );
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

function SourcesTable({ rows }: { rows: CoverageSource[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">Runtime coverage source availability and gaps</caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["Source", "Status", "Count", "Missing Daily", "Updated", "Key"].map((h, i) => (
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
            <tr key={row.name} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
              <td className="px-3 py-3 font-semibold text-slate-900 dark:text-slate-100">
                {sourceLabel(row.name)}
              </td>
              <td className="px-3 py-3 text-right">
                <StatusBadge ok={row.available} />
              </td>
              <td className="px-3 py-3 text-right tabular-nums">
                {row.count ?? "-"}
              </td>
              <td className="px-3 py-3 text-right">
                {row.missing_symbols.length ? (
                  <span className="text-xs text-amber-700 dark:text-amber-300">
                    {row.missing_symbols.slice(0, 5).join(", ")}
                    {row.missing_symbols.length > 5 ? " ..." : ""}
                  </span>
                ) : (
                  <span className="text-slate-400">-</span>
                )}
              </td>
              <td className="px-3 py-3 text-right text-xs text-slate-500">
                {fmtDateTime(row.updated_at)}
              </td>
              <td className="px-3 py-3 text-left font-mono text-xs text-slate-500">
                {row.key ?? "-"}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="px-3 py-8 text-center text-sm text-slate-500" colSpan={6}>
                No coverage sources
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ExperimentTable({ rows }: { rows: ExperimentCoverageRow[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">Latest experiment symbol coverage</caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["Symbol", "Loaded", "Rows", "Start", "End", "Error"].map((h, i) => (
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
            <tr key={row.symbol} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
              <td className="px-3 py-3 font-mono font-semibold text-slate-900 dark:text-slate-100">
                {row.symbol}
              </td>
              <td className="px-3 py-3 text-right">
                <StatusBadge ok={row.loaded} />
              </td>
              <td className="px-3 py-3 text-right tabular-nums">
                {row.rows ?? "-"}
              </td>
              <td className="px-3 py-3 text-right text-xs text-slate-500">
                {row.start ?? "-"}
              </td>
              <td className="px-3 py-3 text-right text-xs text-slate-500">
                {row.end ?? "-"}
              </td>
              <td className="px-3 py-3 text-left text-xs text-amber-700 dark:text-amber-300">
                {row.error ?? "-"}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="px-3 py-8 text-center text-sm text-slate-500" colSpan={6}>
                No latest experiment coverage
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function CoveragePage() {
  const { selectedAsset } = useAssetClass();
  const {
    data,
    isLoading,
    errorMessage,
    refetch,
    dataUpdatedAt,
    isFetching,
  } = useQueryWithError<CoverageResponse>({
    queryKey: ["coverage", selectedAsset],
    queryFn: () =>
      coverageApi.getCoverage({ asset_class: selectedAsset }).then((r) => r.data),
    refetchInterval: 30000,
  });

  const availableSources = data?.sources.filter((s) => s.available).length ?? 0;
  const missingDaily = data?.sources.reduce(
    (acc, source) => acc + source.missing_symbols.length,
    0,
  ) ?? 0;
  const loadedExperiment = data?.experiment_coverage.filter((row) => row.loaded).length ?? 0;

  return (
    <>
      <HeaderBar />
      <div className="mx-auto max-w-[1400px] px-2 pb-24 pt-2 sm:px-4 lg:px-6 lg:pb-2">
        <div className="space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <DatabaseZap className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  Coverage Explorer
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
                onClick={() => refetch()}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 focus-ring dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                aria-label="Refresh coverage"
              >
                <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          {errorMessage && (
            <ErrorMessage message={errorMessage} onRetry={() => refetch()} />
          )}

          {isLoading && !data ? (
            <div role="status" aria-label="Loading coverage sources" className="sr-only">
              Loading coverage sources
            </div>
          ) : null}

          <section className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            <StatCell
              label="Sources Available"
              value={isLoading && !data ? "..." : `${availableSources}/${data?.sources.length ?? 0}`}
            />
            <StatCell
              label="Missing Evidence"
              value={`${data?.missing_evidence.length ?? 0}`}
            />
            <StatCell label="Missing Daily Indicators" value={`${missingDaily}`} />
            <StatCell
              label="Experiment Loaded"
              value={`${loadedExperiment}/${data?.experiment_coverage.length ?? 0}`}
            />
          </section>

          {(data?.missing_evidence.length ?? 0) > 0 && (
            <div
              role="alert"
              className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
            >
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <div className="break-words">
                  Missing evidence: {data?.missing_evidence.join(", ")}
                </div>
              </div>
            </div>
          )}

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Runtime Sources
              </h2>
              <span className="text-sm text-slate-500">
                {data?.sources.length ?? 0} sources
              </span>
            </div>
            <SourcesTable rows={data?.sources ?? []} />
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Latest Experiment Coverage
              </h2>
              <span className="text-sm text-slate-500">
                {data?.experiment_coverage.length ?? 0} symbols
              </span>
            </div>
            <ExperimentTable rows={data?.experiment_coverage ?? []} />
          </section>

          {data?.notes.length ? (
            <div className="text-xs text-slate-500">
              {data.notes.join(" ")}
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
