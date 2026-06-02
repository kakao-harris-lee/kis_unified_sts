"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Clock3,
  FlaskConical,
  RefreshCcw,
  TrendingUp,
} from "lucide-react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getStockBuilderPresetExperiment,
  type ExperimentStatusResponse,
  type ExperimentSummary,
} from "@/lib/api/experiments";

const chartColors = [
  "#ef4444",
  "#2563eb",
  "#16a34a",
  "#ca8a04",
  "#9333ea",
  "#0f766e",
  "#ea580c",
  "#be123c",
  "#4f46e5",
  "#64748b",
  "#0891b2",
];

function formatKrw(value: number): string {
  return `₩${Math.round(value).toLocaleString("ko-KR")}`;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function statusView(status: string) {
  if (status === "completed") {
    return {
      label: "완료",
      icon: CheckCircle2,
      className:
        "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300",
    };
  }
  if (status === "running") {
    return {
      label: "진행 중",
      icon: TrendingUp,
      className:
        "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
    };
  }
  if (status === "waiting_first_run" || status === "upcoming") {
    return {
      label: "대기",
      icon: Clock3,
      className:
        "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
    };
  }
  return {
    label: "확인 필요",
    icon: AlertCircle,
    className: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
  };
}

function StatTile({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof BarChart3;
}) {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
          <div className="mt-1 text-xl font-bold text-slate-900 dark:text-slate-100">
            {value}
          </div>
        </div>
        <Icon className="h-5 w-5 text-slate-500 dark:text-slate-400" aria-hidden="true" />
      </div>
    </div>
  );
}

function SummaryTable({ summaries }: { summaries: ExperimentSummary[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
        <thead className="bg-slate-50 dark:bg-slate-800/70">
          <tr>
            {["순위", "전략", "수익률", "평가자산", "실현", "미실현", "진입", "청산", "보유", "MDD"].map(
              (label, index) => (
                <th
                  key={label}
                  className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${
                    index < 2 ? "text-left" : "text-right"
                  }`}
                >
                  {label}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {summaries.map((item, index) => {
            const positive = item.total_return_pct >= 0;
            return (
              <tr key={item.strategy_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <td className="px-3 py-3 text-slate-500">{index + 1}</td>
                <td className="px-3 py-3">
                  <div className="font-semibold text-slate-900 dark:text-slate-100">
                    {item.strategy_id}
                  </div>
                  <div className="text-xs text-slate-500">{item.strategy_name}</div>
                </td>
                <td className={`px-3 py-3 text-right font-bold ${positive ? "text-profit" : "text-loss"}`}>
                  {item.total_return_pct.toFixed(2)}%
                </td>
                <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">
                  {formatKrw(item.final_equity)}
                </td>
                <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">
                  {formatKrw(item.realized_pnl)}
                </td>
                <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">
                  {formatKrw(item.unrealized_pnl)}
                </td>
                <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">
                  {item.admitted_entries}
                </td>
                <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">
                  {item.closed_trades}
                </td>
                <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">
                  {item.open_positions}
                </td>
                <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">
                  {item.max_drawdown_pct.toFixed(2)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function ExperimentsPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery<ExperimentStatusResponse>({
    queryKey: ["stock-builder-preset-experiment"],
    queryFn: getStockBuilderPresetExperiment,
    refetchInterval: 30000,
  });

  const latest = data?.latest_report;
  const summaries = latest?.summaries ?? [];
  const leader = summaries[0];
  const status = statusView(data?.progress.status ?? "upcoming");
  const StatusIcon = status.icon;

  const chartData = useMemo(() => {
    if (!latest?.equity_curves) return [];
    const byDate = new Map<string, Record<string, string | number>>();
    for (const [strategy, points] of Object.entries(latest.equity_curves)) {
      for (const point of points) {
        const row = byDate.get(point.date) ?? { date: point.date };
        row[strategy] = point.equity;
        byDate.set(point.date, row);
      }
    }
    return Array.from(byDate.values()).sort((a, b) =>
      String(a.date).localeCompare(String(b.date)),
    );
  }, [latest]);

  return (
    <div className="max-w-[1400px] mx-auto px-3 sm:px-5 lg:px-6 py-5 pb-24">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-white">
            <FlaskConical className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              실험 리포트
            </h1>
            <div className="text-sm text-slate-500 dark:text-slate-400">
              {data?.experiment.id ?? "stock builder preset experiment"}
            </div>
          </div>
        </div>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          <RefreshCcw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          새로고침
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
          리포트 API를 불러오지 못했습니다.
        </div>
      )}

      {isLoading && <div className="card p-6 text-sm text-slate-500">불러오는 중...</div>}

      {data && (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div className="card p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">상태</div>
                  <div className={`mt-2 inline-flex items-center gap-2 rounded px-2 py-1 text-sm font-semibold ${status.className}`}>
                    <StatusIcon className="h-4 w-4" />
                    {status.label}
                  </div>
                </div>
                <CalendarClock className="h-5 w-5 text-slate-500" aria-hidden="true" />
              </div>
            </div>
            <StatTile
              label="진행률"
              value={`${data.progress.completed_report_days}/${data.progress.total_scheduled_days}`}
              icon={BarChart3}
            />
            <StatTile
              label="다음 실행"
              value={formatDateTime(data.progress.next_run_at_kst)}
              icon={Clock3}
            />
            <StatTile
              label="최신 리포트"
              value={formatDateTime(data.progress.last_report_at)}
              icon={CheckCircle2}
            />
            <StatTile label="현재 1위" value={leader ? leader.strategy_id : "-"} icon={TrendingUp} />
          </div>

          <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${Math.min(100, data.progress.completion_pct)}%` }}
            />
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
            <div className="space-y-5">
              <section className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                    전략별 성과
                  </h2>
                  <div className="text-sm text-slate-500">{summaries.length} strategies</div>
                </div>
                {summaries.length ? (
                  <SummaryTable summaries={summaries} />
                ) : (
                  <div className="card p-6 text-sm text-slate-500">
                    아직 생성된 실험 리포트가 없습니다.
                  </div>
                )}
              </section>

              {chartData.length > 0 && (
                <section className="space-y-3">
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                    평가자산 추이
                  </h2>
                  <div className="h-80 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData}>
                        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 12 }} width={78} />
                        <Tooltip formatter={(value) => formatKrw(Number(value))} />
                        {summaries.slice(0, 8).map((summary, index) => (
                          <Line
                            key={summary.strategy_id}
                            type="monotone"
                            dataKey={summary.strategy_id}
                            stroke={chartColors[index % chartColors.length]}
                            strokeWidth={2}
                            dot={false}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </section>
              )}
            </div>

            <aside className="space-y-5">
              <section className="card p-4">
                <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                  실험 범위
                </h2>
                <dl className="mt-3 space-y-2 text-sm">
                  <div className="flex justify-between gap-3">
                    <dt className="text-slate-500">기간</dt>
                    <dd className="text-right font-medium text-slate-800 dark:text-slate-200">
                      {data.experiment.start_date} - {data.experiment.end_date}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-slate-500">실행</dt>
                    <dd className="font-medium text-slate-800 dark:text-slate-200">
                      {data.experiment.daily_run_time_kst} KST
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-slate-500">Preset</dt>
                    <dd className="font-medium text-slate-800 dark:text-slate-200">
                      {data.experiment.presets.length}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-slate-500">종목</dt>
                    <dd className="font-medium text-slate-800 dark:text-slate-200">
                      {latest?.experiment.symbols.length ?? data.experiment.fallback_symbols.length}
                    </dd>
                  </div>
                </dl>
              </section>

              <section className="card p-4">
                <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                  리포트 파일
                </h2>
                <div className="mt-3 space-y-2">
                  {data.reports.slice(0, 6).map((report) => (
                    <div key={report.path} className="rounded border border-slate-200 p-3 text-sm dark:border-slate-800">
                      <div className="font-medium text-slate-800 dark:text-slate-200">
                        {report.filename}
                      </div>
                      <div className="mt-1 text-xs text-slate-500">
                        {formatDateTime(report.generated_at ?? report.mtime)}
                      </div>
                    </div>
                  ))}
                  {!data.reports.length && <div className="text-sm text-slate-500">생성된 파일 없음</div>}
                </div>
              </section>

              <section className="card p-4">
                <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                  최근 로그
                </h2>
                {data.latest_log ? (
                  <pre className="mt-3 max-h-64 overflow-auto rounded bg-slate-950 p-3 text-xs leading-5 text-slate-100">
                    {data.latest_log.lines.join("\n")}
                  </pre>
                ) : (
                  <div className="mt-3 text-sm text-slate-500">로그 없음</div>
                )}
              </section>
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
