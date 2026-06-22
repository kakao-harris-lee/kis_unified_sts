"use client";

import {
  Activity,
  AlertTriangle,
  Ban,
  CalendarClock,
  CheckCircle2,
  CircleHelp,
  Clock3,
  ListChecks,
  Newspaper,
  Radio,
  RefreshCcw,
  XCircle,
} from "lucide-react";
import HeaderBar from "@/components/dashboard/HeaderBar";
import ErrorMessage from "@/components/dashboard/ErrorMessage";
import RefreshIndicator from "@/components/dashboard/RefreshIndicator";
import useQueryWithError from "@/hooks/dashboard/useQueryWithError";
import {
  eventContextApi,
  normalizeEventContextDiagnostics,
  type DiagnosticStatus,
  type EventContextDiagnosticsResponse,
  type EventScoreSourceBreakdown,
  type SetupCEvidenceItem,
  type SetupCReasonBucket,
  type SourceTimelineItem,
} from "@/lib/dashboard/eventContext";

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

function fmtAge(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return "-";
  if (seconds < 60) return `${Math.max(0, Math.round(seconds))}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

function fmtCount(v?: number | null): string {
  return v === null || v === undefined ? "-" : v.toLocaleString("ko-KR");
}

function fmtRatio(v?: number | null): string {
  if (v === null || v === undefined) return "-";
  const pct = v <= 1 ? v * 100 : v;
  return `${pct.toFixed(1)}%`;
}

function statusLabel(status: DiagnosticStatus): string {
  const labels: Record<DiagnosticStatus, string> = {
    ok: "ok",
    stale: "stale",
    sparse: "sparse",
    missing: "missing",
    blocked: "blocked",
    error: "error",
    unknown: "unknown",
  };
  return labels[status];
}

function statusClasses(status: DiagnosticStatus): string {
  const classes: Record<DiagnosticStatus, string> = {
    ok: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
    stale: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    sparse: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    missing: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
    blocked: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
    error: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
    unknown: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  };
  return classes[status];
}

function StatusBadgeIcon({ status }: { status: DiagnosticStatus }) {
  const className = "h-3 w-3";
  switch (status) {
    case "ok":
      return <CheckCircle2 className={className} aria-hidden="true" />;
    case "stale":
      return <Clock3 className={className} aria-hidden="true" />;
    case "sparse":
    case "error":
      return <AlertTriangle className={className} aria-hidden="true" />;
    case "missing":
      return <XCircle className={className} aria-hidden="true" />;
    case "blocked":
      return <Ban className={className} aria-hidden="true" />;
    case "unknown":
      return <CircleHelp className={className} aria-hidden="true" />;
  }
}

function StatusBadge({ status }: { status: DiagnosticStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold ${statusClasses(status)}`}
    >
      <StatusBadgeIcon status={status} />
      {statusLabel(status)}
    </span>
  );
}

function StatCell({
  label,
  value,
  detail,
  status,
}: {
  label: string;
  value: string;
  detail?: string;
  status?: DiagnosticStatus;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
          {label}
        </div>
        {status ? <StatusBadge status={status} /> : null}
      </div>
      <div className="mt-1 truncate text-lg font-bold text-slate-900 dark:text-slate-100">
        {value}
      </div>
      {detail ? <div className="mt-1 truncate text-xs text-slate-500">{detail}</div> : null}
    </div>
  );
}

function LoadingRows({ rows = 3 }: { rows?: number }) {
  return (
    <div className="divide-y divide-slate-100 dark:divide-slate-800">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="grid gap-2 px-3 py-3 md:grid-cols-5">
          <div className="h-4 rounded bg-slate-100 dark:bg-slate-800" />
          <div className="h-4 rounded bg-slate-100 dark:bg-slate-800" />
          <div className="h-4 rounded bg-slate-100 dark:bg-slate-800" />
          <div className="h-4 rounded bg-slate-100 dark:bg-slate-800" />
          <div className="h-4 rounded bg-slate-100 dark:bg-slate-800" />
        </div>
      ))}
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="px-3 py-8 text-center text-sm text-slate-500 dark:text-slate-400">
      {message}
    </div>
  );
}

function ScoreSourceTable({
  rows,
  isLoading,
}: {
  rows: EventScoreSourceBreakdown[];
  isLoading: boolean;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <caption className="sr-only">Event score source freshness and counts</caption>
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["Source", "Status", "Scores", "Latest"].map((h, i) => (
              <th
                key={h}
                scope="col"
                className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${
                  i === 0 ? "text-left" : "text-right"
                }`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {isLoading ? (
            <tr>
              <td colSpan={4}>
                <LoadingRows rows={2} />
              </td>
            </tr>
          ) : rows.length ? (
            rows.map((row) => (
              <tr key={row.source} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="px-3 py-3 font-semibold text-slate-900 dark:text-slate-100">
                  {row.source}
                </td>
                <td className="px-3 py-3 text-right">
                  <StatusBadge status={row.status} />
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  {fmtCount(row.count)}
                </td>
                <td className="px-3 py-3 text-right text-xs text-slate-500">
                  {fmtDateTime(row.latest_score_at)}
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={4}>
                <EmptyState message="No event-score source breakdown" />
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function SourceTimeline({
  rows,
  isLoading,
}: {
  rows: SourceTimelineItem[];
  isLoading: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      {isLoading ? (
        <LoadingRows rows={4} />
      ) : rows.length ? (
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row) => {
            return (
              <div
                key={`${row.source}-${row.key ?? row.label}`}
                className="grid gap-3 px-3 py-3 md:grid-cols-[minmax(220px,1.2fr)_auto_minmax(160px,0.8fr)_minmax(160px,1fr)] md:items-center"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    <SourceKindIcon kind={row.kind} />
                  </div>
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-slate-900 dark:text-slate-100">
                      {row.label}
                    </div>
                    <div className="truncate font-mono text-xs text-slate-500">
                      {row.key ?? row.source}
                    </div>
                  </div>
                </div>
                <div className="md:text-right">
                  <StatusBadge status={row.status} />
                </div>
                <div className="text-sm text-slate-600 dark:text-slate-300 md:text-right">
                  <span className="font-medium tabular-nums">{fmtCount(row.count)}</span>
                  <span className="text-slate-400"> · age {fmtAge(row.age_seconds)}</span>
                </div>
                <div className="text-xs text-slate-500 md:text-right">
                  <div>{fmtDateTime(row.last_seen_at)}</div>
                  {row.details ? <div className="truncate">{row.details}</div> : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyState message="No news or macro source timeline" />
      )}
    </div>
  );
}

function SourceKindIcon({ kind }: { kind: SourceTimelineItem["kind"] }) {
  const className = "h-4 w-4";
  switch (kind) {
    case "news":
      return <Newspaper className={className} aria-hidden="true" />;
    case "macro":
      return <CalendarClock className={className} aria-hidden="true" />;
    case "scoring":
      return <Radio className={className} aria-hidden="true" />;
    case "event":
      return <Activity className={className} aria-hidden="true" />;
    case "unknown":
      return <CircleHelp className={className} aria-hidden="true" />;
  }
}

type EvidenceKind = "candidates" | "blocked" | "missing";

function EvidenceKindIcon({ kind }: { kind: EvidenceKind }) {
  const className = "h-4 w-4 text-slate-500";
  switch (kind) {
    case "candidates":
      return <ListChecks className={className} aria-hidden="true" />;
    case "blocked":
      return <Ban className={className} aria-hidden="true" />;
    case "missing":
      return <AlertTriangle className={className} aria-hidden="true" />;
  }
}

function EvidenceList({
  title,
  icon,
  rows,
  emptyMessage,
  isLoading,
}: {
  title: string;
  icon: EvidenceKind;
  rows: SetupCEvidenceItem[];
  emptyMessage: string;
  isLoading: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <EvidenceKindIcon kind={icon} />
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            {title}
          </h3>
        </div>
        <span className="text-xs text-slate-500">{rows.length}</span>
      </div>
      {isLoading ? (
        <LoadingRows rows={3} />
      ) : rows.length ? (
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row, index) => (
            <div key={row.id ?? `${row.timestamp ?? "row"}-${index}`} className="px-3 py-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-slate-900 dark:text-slate-100">
                      {row.symbol ?? row.event_id ?? "event"}
                    </span>
                    {row.direction ? (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] font-semibold uppercase text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                        {row.direction}
                      </span>
                    ) : null}
                    <StatusBadge status={row.status} />
                  </div>
                  <div className="mt-1 text-sm text-slate-700 dark:text-slate-300">
                    {row.reason ?? row.details ?? row.event_type ?? "No reason supplied"}
                  </div>
                  {row.evidence.length ? (
                    <div className="mt-1 text-xs text-slate-500">
                      {row.evidence.join(", ")}
                    </div>
                  ) : null}
                </div>
                <div className="shrink-0 text-right text-xs text-slate-500">
                  <div>{fmtDateTime(row.timestamp)}</div>
                  <div>
                    {row.score !== null ? `score ${row.score}` : ""}
                    {row.impact_tier !== null ? ` tier ${row.impact_tier}` : ""}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message={emptyMessage} />
      )}
    </div>
  );
}

function ReasonDistribution({
  rows,
  isLoading,
}: {
  rows: SetupCReasonBucket[];
  isLoading: boolean;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2 dark:border-slate-800">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
          Blocked Reason Distribution
        </h3>
        <span className="text-xs text-slate-500">{rows.length} reasons</span>
      </div>
      {isLoading ? (
        <LoadingRows rows={3} />
      ) : rows.length ? (
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map((row) => (
            <div
              key={row.reason}
              className="grid gap-2 px-3 py-3 text-sm sm:grid-cols-[1fr_auto_auto] sm:items-center"
            >
              <div className="min-w-0 truncate font-medium text-slate-900 dark:text-slate-100">
                {row.reason}
              </div>
              <div className="text-right tabular-nums text-slate-700 dark:text-slate-300">
                {row.count}
              </div>
              <div className="text-right text-xs text-slate-500">
                {fmtDateTime(row.latest_at)}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState message="No blocked Setup C reasons" />
      )}
    </div>
  );
}

function uniqueMessages(data?: EventContextDiagnosticsResponse): string[] {
  if (!data) return [];
  const messages = new Set<string>();
  for (const message of data.missing_evidence) messages.add(message);
  for (const message of data.event_scores.warnings) messages.add(message);
  for (const item of data.setup_c.missing_evidence) {
    if (item.reason) messages.add(item.reason);
    if (item.details) messages.add(item.details);
    for (const evidence of item.evidence) messages.add(evidence);
  }
  return [...messages];
}

export default function EventContextPage() {
  const {
    data,
    isLoading,
    errorMessage,
    refetch,
    dataUpdatedAt,
    isFetching,
  } = useQueryWithError<EventContextDiagnosticsResponse>({
    queryKey: ["event-context-diagnostics", "futures"],
    queryFn: () =>
      eventContextApi
        .getDiagnostics({ asset_class: "futures" })
        .then((r) => normalizeEventContextDiagnostics(r.data)),
    refetchInterval: 30000,
  });

  const eventScores = data?.event_scores;
  const setupC = data?.setup_c;
  const missingMessages = uniqueMessages(data);
  const tierSummary = eventScores?.by_impact_tier
    ? Object.entries(eventScores.by_impact_tier)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([tier, count]) => `T${tier}: ${count}`)
        .join(" · ")
    : "";

  return (
    <>
      <HeaderBar />
      <div className="mx-auto max-w-[1400px] px-2 pb-24 pt-2 sm:px-4 lg:px-6 lg:pb-2">
        <div className="space-y-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <CalendarClock className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                  Event Context Diagnostics
                </h1>
                <p className="text-sm text-slate-500">
                  {data
                    ? `${data.asset_class} · ${fmtDateTime(data.generated_at)}`
                    : "futures · Setup C source health"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <RefreshIndicator
                lastUpdated={dataUpdatedAt}
                isRefreshing={isFetching}
                staleThresholdSeconds={90}
              />
              <button
                type="button"
                onClick={() => refetch()}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition hover:bg-slate-50 focus-ring dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300"
                aria-label="Refresh event context diagnostics"
              >
                <RefreshCcw className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          {errorMessage && (
            <ErrorMessage message={errorMessage} onRetry={() => refetch()} />
          )}

          {isLoading && !data ? (
            <div role="status" aria-label="Loading event context diagnostics" className="sr-only">
              Loading event context diagnostics
            </div>
          ) : null}

          <section className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
            <StatCell
              label="Event Score Freshness"
              value={isLoading && !eventScores ? "..." : fmtAge(eventScores?.age_seconds)}
              detail={`latest ${fmtDateTime(eventScores?.latest_score_at)}`}
              status={eventScores?.status}
            />
            <StatCell
              label="Event Score Volume"
              value={
                isLoading && !eventScores
                  ? "..."
                  : `${fmtCount(eventScores?.recent_count)} recent / ${fmtCount(eventScores?.total_count)} total`
              }
              detail={tierSummary || "impact tiers unavailable"}
            />
            <StatCell
              label="Sparsity"
              value={
                isLoading && !eventScores
                  ? "..."
                  : eventScores?.sparse
                    ? "Sparse"
                    : eventScores?.status === "unknown"
                      ? "Unknown"
                      : "Usable"
              }
              detail={`ratio ${fmtRatio(eventScores?.sparsity_ratio)}`}
              status={
                eventScores?.sparse
                  ? "sparse"
                  : eventScores?.status === "missing"
                    ? "missing"
                    : eventScores?.status
              }
            />
            <StatCell
              label="Setup C Candidates"
              value={isLoading && !setupC ? "..." : fmtCount(setupC?.candidate_count)}
              detail={`${fmtCount(setupC?.blocked_count)} blocked · ${fmtCount(setupC?.missing_count)} missing`}
              status={
                setupC?.candidate_count
                  ? "ok"
                  : (setupC?.missing_count ?? 0) > 0
                    ? "missing"
                    : "unknown"
              }
            />
          </section>

          {missingMessages.length > 0 && (
            <div
              role="alert"
              className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
            >
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                <div className="break-words">Missing event context evidence: {missingMessages.join(", ")}</div>
              </div>
            </div>
          )}

          <section className="grid gap-4 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                  Event Score Sources
                </h2>
                <span className="text-sm text-slate-500">
                  {eventScores?.by_source.length ?? 0} sources
                </span>
              </div>
              <ScoreSourceTable
                rows={eventScores?.by_source ?? []}
                isLoading={isLoading && !data}
              />
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                  News / Macro Timeline
                </h2>
                <span className="text-sm text-slate-500">
                  {data?.source_timeline.length ?? 0} sources
                </span>
              </div>
              <SourceTimeline rows={data?.source_timeline ?? []} isLoading={isLoading && !data} />
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                  Setup C Evidence
                </h2>
                <p className="text-sm text-slate-500">
                  {setupC
                    ? `${setupC.strategy} · window ${fmtCount(setupC.window_minutes)}m · tier <= ${fmtCount(setupC.min_impact_tier)} · last eval ${fmtDateTime(setupC.last_eval_at)}`
                    : "Candidate, block, and missing-source evidence"}
                </p>
              </div>
              {setupC?.last_reject_reason ? (
                <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                  latest reject: {setupC.last_reject_reason}
                </span>
              ) : null}
            </div>

            <div className="grid gap-4 xl:grid-cols-3">
              <EvidenceList
                title="Candidates"
                icon="candidates"
                rows={setupC?.candidates ?? []}
                emptyMessage="No Setup C candidates in the diagnostics window"
                isLoading={isLoading && !data}
              />
              <EvidenceList
                title="Blocked"
                icon="blocked"
                rows={setupC?.blocked ?? []}
                emptyMessage="No Setup C blocks reported"
                isLoading={isLoading && !data}
              />
              <EvidenceList
                title="Missing Evidence"
                icon="missing"
                rows={setupC?.missing_evidence ?? []}
                emptyMessage="No missing event-source evidence reported"
                isLoading={isLoading && !data}
              />
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)]">
            <ReasonDistribution
              rows={setupC?.blocked_reason_distribution ?? []}
              isLoading={isLoading && !data}
            />
            <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-slate-500" aria-hidden="true" />
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Operator Notes
                </h3>
              </div>
              {data?.notes.length || setupC?.notes.length ? (
                <div className="mt-3 space-y-2 text-sm text-slate-600 dark:text-slate-300">
                  {[...(data?.notes ?? []), ...(setupC?.notes ?? [])].map((note) => (
                    <p key={note}>{note}</p>
                  ))}
                </div>
              ) : (
                <div className="mt-3 text-sm text-slate-500">
                  No additional notes from diagnostics.
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}
