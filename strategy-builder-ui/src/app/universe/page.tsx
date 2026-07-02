"use client";

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ListFilter,
  Pin,
  RefreshCcw,
  RotateCw,
  Trash2,
  XCircle,
} from "lucide-react";
import HeaderBar from "@/components/dashboard/HeaderBar";
import ErrorMessage from "@/components/dashboard/ErrorMessage";
import RefreshIndicator from "@/components/dashboard/RefreshIndicator";
import SymbolLabel from "@/components/dashboard/SymbolLabel";
import useQueryWithError from "@/hooks/dashboard/useQueryWithError";
import { useToast } from "@/components/ui";
import { universeApi } from "@/lib/dashboard/api";
import type {
  UniverseOverridePayload,
  UniverseResponse,
  UniverseRow,
  UniverseSource,
} from "@/lib/dashboard/universe";
import { QUERY_INTERVALS_MS } from "@/lib/dashboard/queryIntervals";

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

function fmtScore(v?: number | null): string {
  if (v === null || v === undefined) return "-";
  const score = Math.abs(v) <= 1 ? v * 100 : v;
  return `${score.toFixed(1)}`;
}

function sourceLabel(value: string): string {
  const labels: Record<string, string> = {
    manual_include: "Pinned",
    manual_exclude: "Blocked",
    trade_targets: "Trade",
    daily_watchlist: "Watchlist",
    screener_universe: "Screener",
    theme_targets: "Theme",
    open_position: "Position",
  };
  return labels[value] ?? value;
}

function StateBadge({ ok, label }: { ok: boolean; label: string }) {
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
      {label}
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

function SourceTable({ rows }: { rows: UniverseSource[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">Trading universe source freshness</caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["Source", "State", "Count", "Updated", "Age", "Key"].map((h, i) => (
              <th
                key={h}
                scope="col"
                className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${
                  i === 0 || i === 5 ? "text-left" : "text-right"
                }`}
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
                <StateBadge
                  ok={row.available && !row.stale}
                  label={!row.available ? "missing" : row.stale ? "stale" : "fresh"}
                />
              </td>
              <td className="px-3 py-3 text-right tabular-nums">{row.count ?? "-"}</td>
              <td className="px-3 py-3 text-right text-xs text-slate-500">
                {fmtDateTime(row.updated_at)}
              </td>
              <td className="px-3 py-3 text-right text-xs tabular-nums text-slate-500">
                {row.age_seconds === null || row.age_seconds === undefined
                  ? "-"
                  : `${row.age_seconds}s`}
              </td>
              <td className="px-3 py-3 text-left font-mono text-xs text-slate-500">
                {row.key}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SourceBadges({ sources }: { sources: string[] }) {
  return (
    <div className="flex flex-wrap justify-end gap-1">
      {sources.map((source) => (
        <span
          key={source}
          className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300"
        >
          {sourceLabel(source)}
        </span>
      ))}
    </div>
  );
}

function UniverseTable({
  rows,
  onAction,
  busy,
}: {
  rows: UniverseRow[];
  onAction: (row: UniverseRow, action: UniverseOverridePayload["action"]) => void;
  busy: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">Managed trading universe symbols</caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["Rank", "Symbol", "Entry", "Market Data", "Score", "Daily", "Sources", "Reason", "Actions"].map((h, i) => (
              <th
                key={h}
                scope="col"
                className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${
                  i === 1 || i === 7 ? "text-left" : "text-right"
                }`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row) => (
            <tr key={row.code} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
              <td className="px-3 py-3 text-right tabular-nums text-slate-500">
                {row.rank ?? "-"}
              </td>
              <td className="px-3 py-3">
                <SymbolLabel
                  code={row.code}
                  name={row.name}
                  nameClassName="text-slate-900 dark:text-slate-100"
                />
              </td>
              <td className="px-3 py-3 text-right">
                <StateBadge
                  ok={row.new_entries_allowed}
                  label={row.new_entries_allowed ? "active" : "blocked"}
                />
              </td>
              <td className="px-3 py-3 text-right">
                <StateBadge
                  ok={row.market_data_required}
                  label={row.market_data_required ? "subscribed" : "off"}
                />
              </td>
              <td className="px-3 py-3 text-right tabular-nums">{fmtScore(row.score)}</td>
              <td className="px-3 py-3 text-right text-xs">{row.daily_indicator}</td>
              <td className="px-3 py-3 text-right">
                <SourceBadges sources={row.sources} />
              </td>
              <td className="max-w-[280px] px-3 py-3 text-left text-xs text-slate-600 dark:text-slate-300">
                <span className="line-clamp-2">
                  {row.blocked_reason ?? row.override_detail?.reason ?? "-"}
                </span>
              </td>
              <td className="px-3 py-3 text-right">
                <div className="inline-flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => onAction(row, "include")}
                    disabled={busy}
                    className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 text-slate-600 transition hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                    aria-label={`Pin ${row.code}`}
                    title="Pin"
                  >
                    <Pin className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onAction(row, "exclude")}
                    disabled={busy}
                    className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 text-slate-600 transition hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                    aria-label={`Block ${row.code}`}
                    title="Block"
                  >
                    <Ban className="h-4 w-4" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onAction(row, "remove")}
                    disabled={busy}
                    className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 text-slate-600 transition hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                    aria-label={`Remove override for ${row.code}`}
                    title="Remove override"
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="px-3 py-8 text-center text-sm text-slate-500" colSpan={9}>
                No trading universe symbols
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function UniversePage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [symbol, setSymbol] = useState("");
  const [name, setName] = useState("");
  const [reason, setReason] = useState("");
  const [ttlHours, setTtlHours] = useState(24);

  const {
    data,
    isLoading,
    errorMessage,
    refetch,
    dataUpdatedAt,
    isFetching,
  } = useQueryWithError<UniverseResponse>({
    queryKey: ["trading-universe"],
    queryFn: () => universeApi.getUniverse().then((r) => r.data),
    refetchInterval: QUERY_INTERVALS_MS.normal,
  });

  const mutation = useMutation({
    mutationFn: (payload: UniverseOverridePayload) =>
      universeApi.updateOverride(payload).then((r) => r.data),
    onSuccess: (next) => {
      queryClient.setQueryData(["trading-universe"], next);
      toast.success("Universe updated");
      setReason("");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Universe update failed");
    },
  });

  const recompute = useMutation({
    mutationFn: () => universeApi.recompute().then((r) => r.data),
    onSuccess: (next) => {
      queryClient.setQueryData(["trading-universe"], next);
      toast.success("Universe recomputed");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Universe recompute failed");
    },
  });

  const activeCount = data?.codes.length ?? 0;
  const marketDataCount = data?.market_data_codes.length ?? 0;
  const blockedCount = useMemo(
    () => data?.rows.filter((row) => row.override === "manual_exclude").length ?? 0,
    [data],
  );
  const staleSources = data?.sources.filter((source) => source.stale).length ?? 0;
  const busy = mutation.isPending || recompute.isPending;

  const submit = (
    action: UniverseOverridePayload["action"],
    selected?: Pick<UniverseRow, "code" | "name">,
  ) => {
    const targetSymbol = (selected?.code ?? symbol).trim();
    const targetName = selected?.name ?? name;
    if (!targetSymbol) {
      toast.error("Symbol is required");
      return;
    }
    if (action !== "remove" && !reason.trim()) {
      toast.error("Reason is required");
      return;
    }
    mutation.mutate({
      action,
      symbol: targetSymbol,
      name: targetName || undefined,
      reason: action === "remove" ? reason || undefined : reason.trim(),
      ttl_seconds: Math.max(1, ttlHours) * 3600,
      operator: "dashboard",
    });
  };

  const onRowAction = (row: UniverseRow, action: UniverseOverridePayload["action"]) => {
    setSymbol(row.code);
    setName(row.name ?? "");
    submit(action, row);
  };

  return (
    <>
      <HeaderBar />
      <div className="mx-auto max-w-[1500px] px-2 pb-24 pt-2 sm:px-4 lg:px-6 lg:pb-2">
        <div className="space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <ListFilter className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  Trading Universe
                </h1>
                <p className="text-sm text-slate-500">
                  {data ? `${data.asset_class} · ${fmtDateTime(data.generated_at)}` : "stock"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <RefreshIndicator
                lastUpdated={dataUpdatedAt}
                isRefreshing={isFetching || recompute.isPending}
              />
              <button
                type="button"
                onClick={() => recompute.mutate()}
                disabled={busy}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                aria-label="Recompute universe"
                title="Recompute"
              >
                <RotateCw className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => refetch()}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                aria-label="Refresh universe"
                title="Refresh"
              >
                <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          {errorMessage && <ErrorMessage message={errorMessage} onRetry={() => refetch()} />}

          {isLoading && !data ? (
            <div role="status" aria-label="Loading trading universe" className="sr-only">
              Loading trading universe
            </div>
          ) : null}

          <section className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            <StatCell label="Active Entries" value={`${activeCount}/${data?.max_symbols ?? 0}`} />
            <StatCell label="Market Data" value={`${marketDataCount}`} />
            <StatCell label="Manual Blocks" value={`${blockedCount}`} />
            <StatCell label="Stale Sources" value={`${staleSources}`} />
          </section>

          {(data?.notes.length ?? 0) > 0 && (
            <div
              role="alert"
              className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
            >
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <div className="break-words">{data?.notes.join(", ")}</div>
              </div>
            </div>
          )}

          <section className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <div className="grid gap-2 lg:grid-cols-[140px_180px_1fr_120px_auto]">
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Symbol
                <input
                  value={symbol}
                  onChange={(event) => setSymbol(event.target.value)}
                  className="mt-1 h-9 w-full rounded border border-slate-200 bg-white px-2 font-mono text-sm text-slate-900 outline-none transition focus:border-primary dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  placeholder="005930"
                />
              </label>
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Name
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="mt-1 h-9 w-full rounded border border-slate-200 bg-white px-2 text-sm text-slate-900 outline-none transition focus:border-primary dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  placeholder="삼성전자"
                />
              </label>
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Reason
                <input
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  className="mt-1 h-9 w-full rounded border border-slate-200 bg-white px-2 text-sm text-slate-900 outline-none transition focus:border-primary dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                  placeholder="operator override"
                />
              </label>
              <label className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Hours
                <input
                  type="number"
                  min={1}
                  max={168}
                  value={ttlHours}
                  onChange={(event) => setTtlHours(Number(event.target.value))}
                  className="mt-1 h-9 w-full rounded border border-slate-200 bg-white px-2 text-right text-sm text-slate-900 outline-none transition focus:border-primary dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                />
              </label>
              <div className="flex items-end gap-1">
                <button
                  type="button"
                  onClick={() => submit("include")}
                  disabled={busy}
                  className="inline-flex h-9 w-9 items-center justify-center rounded border border-slate-200 text-slate-700 transition hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                  aria-label="Pin symbol"
                  title="Pin"
                >
                  <Pin className="h-4 w-4" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={() => submit("exclude")}
                  disabled={busy}
                  className="inline-flex h-9 w-9 items-center justify-center rounded border border-slate-200 text-slate-700 transition hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                  aria-label="Block symbol"
                  title="Block"
                >
                  <Ban className="h-4 w-4" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={() => submit("remove")}
                  disabled={busy}
                  className="inline-flex h-9 w-9 items-center justify-center rounded border border-slate-200 text-slate-700 transition hover:bg-slate-50 disabled:opacity-40 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                  aria-label="Remove symbol override"
                  title="Remove override"
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Effective Universe
              </h2>
              <span className="text-sm text-slate-500">{data?.rows.length ?? 0} symbols</span>
            </div>
            <UniverseTable rows={data?.rows ?? []} onAction={onRowAction} busy={busy} />
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Source Freshness
              </h2>
              <span className="text-sm text-slate-500">{data?.sources.length ?? 0} sources</span>
            </div>
            <SourceTable rows={data?.sources ?? []} />
          </section>
        </div>
      </div>
    </>
  );
}
