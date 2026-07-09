"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  FlaskConical,
  Loader2,
  Play,
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
  getExperimentJob,
  getExperimentStrategies,
  getLatestExperiment,
  getLatestExperimentPaperComparison,
  runExperiment,
  type ExperimentPaperComparisonRow,
  type ExperimentJob,
  type ExperimentRunReport,
  type RunStrategySummary,
  type StrategyStatus,
} from "@/lib/api/experiments";
import { QUERY_INTERVALS_MS } from "@/lib/dashboard/queryIntervals";
import HeuristicProgressBar from "./components/HeuristicProgressBar";

const chartColors = [
  "#ef4444", "#2563eb", "#16a34a", "#ca8a04", "#9333ea",
  "#0f766e", "#ea580c", "#be123c", "#4f46e5", "#64748b", "#0891b2",
];

function fmtPct(v: number | null | undefined): string {
  return v === null || v === undefined ? "-" : `${v.toFixed(2)}%`;
}
function fmtNum(v: number | null | undefined, d = 2): string {
  return v === null || v === undefined ? "-" : v.toFixed(d);
}
function fmtKrw(v: number | null | undefined): string {
  return v === null || v === undefined ? "-" : `₩${Math.round(v).toLocaleString("ko-KR")}`;
}
function fmtSigned(v: number | null | undefined, d = 2): string {
  if (v === null || v === undefined) return "-";
  return `${v >= 0 ? "+" : ""}${v.toFixed(d)}`;
}
function fmtDateTime(v?: string | null): string {
  if (!v) return "-";
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? v : d.toLocaleString("ko-KR", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

function CompareStatusChip({ status }: { status: ExperimentPaperComparisonRow["status"] }) {
  const map = {
    aligned: { label: "aligned", cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" },
    watch: { label: "watch", cls: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300" },
    fail: { label: "fail", cls: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300" },
    insufficient_data: { label: "insufficient", cls: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300" },
  }[status];
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${map.cls}`}>
      {map.label}
    </span>
  );
}

function StatusChip({ status }: { status: "ok" | "skipped" | "error" }) {
  const map = {
    ok: { label: "정상", cls: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300" },
    skipped: { label: "건너뜀", cls: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300" },
    error: { label: "오류", cls: "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300" },
  }[status];
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${map.cls}`}>
      {map.label}
    </span>
  );
}

function ComparePanel({
  row,
  isLoading,
  selectedStrategy,
}: {
  row?: ExperimentPaperComparisonRow;
  isLoading: boolean;
  selectedStrategy: string | null;
}) {
  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-500 dark:border-slate-800 dark:bg-slate-900">
        paper 비교 로딩 중...
      </div>
    );
  }
  if (!row) {
    if (!selectedStrategy) return null;
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
        <span className="font-semibold">{selectedStrategy}</span> missing_evidence: comparison_row
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-center gap-2">
        <CompareStatusChip status={row.status} />
        <span className="font-semibold text-slate-900 dark:text-slate-100">{row.strategy_id}</span>
        <span className="text-xs text-slate-500">backtest vs paper</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div>
          <div className="text-xs text-slate-500">Paper 거래</div>
          <div className="font-semibold text-slate-900 dark:text-slate-100">{row.paper.trade_count}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Paper 승률</div>
          <div className="font-semibold text-slate-900 dark:text-slate-100">{fmtPct(row.paper.win_rate_pct)}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500">Paper PnL</div>
          <div className={`font-semibold ${(row.paper.total_pnl ?? 0) >= 0 ? "text-profit" : "text-loss"}`}>{fmtKrw(row.paper.total_pnl)}</div>
        </div>
        <div>
          <div className="text-xs text-slate-500">승률 차이</div>
          <div className="font-semibold text-slate-900 dark:text-slate-100">
            {row.deltas.win_rate_pct === null ? "-" : `${fmtSigned(row.deltas.win_rate_pct)}pp`}
          </div>
        </div>
      </div>
      {row.missing_evidence.length > 0 && (
        <div className="mt-3 rounded border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
          missing_evidence: {row.missing_evidence.join(", ")}
        </div>
      )}
      {row.paper.latest_exit_time && (
        <div className="mt-2 text-xs text-slate-500">최근 paper 종료: {fmtDateTime(row.paper.latest_exit_time)}</div>
      )}
    </div>
  );
}

function SummaryTable({
  summaries,
  selectedCompare,
  compareRows,
  compareLoading,
  onCompare,
}: {
  summaries: RunStrategySummary[];
  selectedCompare: string | null;
  compareRows: ExperimentPaperComparisonRow[];
  compareLoading: boolean;
  onCompare: (strategyId: string) => void;
}) {
  const selectedRow = compareRows.find((r) => r.strategy_id === selectedCompare);

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
          <thead className="bg-slate-50 dark:bg-slate-800/70">
            <tr>
              {["전략", "TF", "수익률", "Sharpe", "MDD", "승률", "거래", "평가자산", "Paper"].map((h, i) => (
                <th key={h} className={`px-3 py-2 font-semibold text-slate-600 dark:text-slate-300 ${i === 0 ? "text-left" : "text-right"}`}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {summaries.map((s) => {
              const positive = (s.total_return_pct ?? 0) >= 0;
              const compareRow = compareRows.find((r) => r.strategy_id === s.strategy_id);
              return (
                <tr key={s.strategy_id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  <td className="px-3 py-3">
                    <div className="font-semibold text-slate-900 dark:text-slate-100">{s.strategy_id}</div>
                    <div className="text-xs text-slate-500">{s.strategy_name}</div>
                  </td>
                  <td className="px-3 py-3 text-right text-xs text-slate-500">{s.timeframe}</td>
                  <td className={`px-3 py-3 text-right font-bold ${positive ? "text-profit" : "text-loss"}`}>{fmtPct(s.total_return_pct)}</td>
                  <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">{fmtNum(s.sharpe_ratio)}</td>
                  <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">{fmtPct(s.max_drawdown_pct)}</td>
                  <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">{s.win_rate_pct.toFixed(0)}%</td>
                  <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">{s.closed_trades}</td>
                  <td className="px-3 py-3 text-right text-slate-700 dark:text-slate-200">{fmtKrw(s.final_equity)}</td>
                  <td className="px-3 py-3 text-right">
                    <button
                      onClick={() => onCompare(s.strategy_id)}
                      className="inline-flex items-center gap-1 rounded border border-slate-300 px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
                    >
                      {selectedCompare === s.strategy_id && compareLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                      {compareRow ? <CompareStatusChip status={compareRow.status} /> : "비교"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <ComparePanel
        row={selectedRow}
        isLoading={compareLoading && !!selectedCompare && !selectedRow}
        selectedStrategy={selectedCompare}
      />
    </div>
  );
}

function ReportView({ report }: { report: ExperimentRunReport }) {
  const [selectedCompare, setSelectedCompare] = useState<string | null>(null);
  const chartData = useMemo(() => {
    const byDate = new Map<string, Record<string, string | number>>();
    for (const [sid, points] of Object.entries(report.equity_curves)) {
      for (const p of points) {
        const row = byDate.get(p.date) ?? { date: p.date };
        row[sid] = p.equity;
        byDate.set(p.date, row);
      }
    }
    return Array.from(byDate.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [report]);
  const comparison = useQuery({
    queryKey: ["experiment-paper-comparison", report.experiment.id],
    queryFn: getLatestExperimentPaperComparison,
    enabled: !!selectedCompare,
    staleTime: 30000,
  });

  const notOk = report.status_by_strategy.filter((s) => s.status !== "ok");
  const coverage = Object.entries(report.data_coverage ?? {});
  const loadedCount = coverage.filter(([, v]) => v.loaded).length;
  const noData = coverage.filter(([, v]) => !v.loaded);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="card p-3">
          <div className="text-xs text-slate-500">실험 ID</div>
          <div className="mt-1 text-sm font-semibold truncate">{report.experiment.id}</div>
        </div>
        <div className="card p-3">
          <div className="text-xs text-slate-500">기간</div>
          <div className="mt-1 text-sm font-medium">{report.experiment.start_date} ~ {report.experiment.end_date}</div>
        </div>
        <div className="card p-3">
          <div className="text-xs text-slate-500">종목</div>
          <div className="mt-1 text-sm font-medium">{report.experiment.symbols.length}</div>
        </div>
        <div className="card p-3">
          <div className="text-xs text-slate-500">생성</div>
          <div className="mt-1 text-sm font-medium">{fmtDateTime(report.experiment.generated_at)}</div>
        </div>
      </div>

      {notOk.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs dark:border-amber-900 dark:bg-amber-950/30">
          {notOk.map((s: StrategyStatus) => (
            <div key={s.strategy_id} className="flex items-center gap-2 py-0.5 text-amber-800 dark:text-amber-200">
              <StatusChip status={s.status} />
              <span className="font-medium">{s.strategy_id}</span>
              <span className="text-amber-700/80 dark:text-amber-300/80 truncate">{s.error}</span>
            </div>
          ))}
        </div>
      )}

      {coverage.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-700 dark:text-slate-200">데이터 커버리지</span>
            <span className="text-slate-500">{loadedCount}/{coverage.length} 종목 로드됨</span>
          </div>
          {noData.length > 0 && (
            <div className="mt-1 text-slate-500">
              데이터 없음: {noData.map(([sym, v]) => `${sym} (${v.error ?? "no_data"})`).join(", ")}
              <span className="ml-1 text-slate-400">— 분봉 데이터는 KIS 제약으로 최근 ~30일/유니버스 종목만 제공됩니다.</span>
            </div>
          )}
        </div>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">전략별 성과</h2>
          <span className="text-sm text-slate-500">{report.summaries.length} strategies</span>
        </div>
        {report.summaries.length ? (
          <SummaryTable
            summaries={report.summaries}
            selectedCompare={selectedCompare}
            compareRows={comparison.data?.comparisons ?? []}
            compareLoading={comparison.isLoading || comparison.isFetching}
            onCompare={setSelectedCompare}
          />
        ) : (
          <div className="card p-6 text-sm text-slate-500">정상 실행된 전략이 없습니다 (위 상태 참조).</div>
        )}
      </section>

      {chartData.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">평가자산 추이 (포트폴리오)</h2>
          <div className="h-80 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} width={78} />
                <Tooltip formatter={(v) => fmtKrw(Number(v))} />
                {report.summaries.map((s, i) => (
                  <Line key={s.strategy_id} type="monotone" dataKey={s.strategy_id}
                    stroke={chartColors[i % chartColors.length]} strokeWidth={2} dot={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
    </div>
  );
}

export default function ExperimentsPage() {
  const [showForm, setShowForm] = useState(false);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [symbols, setSymbols] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);

  const latest = useQuery({
    queryKey: ["experiment-latest"],
    queryFn: getLatestExperiment,
    refetchInterval: QUERY_INTERVALS_MS.experiments,
  });
  const catalog = useQuery({
    queryKey: ["experiment-strategies"],
    queryFn: getExperimentStrategies,
  });
  const job = useQuery<ExperimentJob>({
    queryKey: ["experiment-job", jobId],
    queryFn: () => getExperimentJob(jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "done" || s === "failed" ? false : 2500;
    },
  });

  const runMut = useMutation({
    mutationFn: runExperiment,
    onSuccess: (j) => setJobId(j.job_id),
  });

  const launch = () => {
    const picked = (catalog.data?.strategies ?? [])
      .filter((s) => selected[s.name])
      .map((s) => ({ type: "registry", name: s.name }));
    const syms = symbols.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
    runMut.mutate({
      ...(picked.length ? { strategies: picked } : {}),
      ...(syms.length ? { symbols: syms } : {}),
      ...(start ? { start } : {}),
      ...(end ? { end } : {}),
    });
  };

  const jobReport = job.data?.status === "done" ? job.data.report : null;
  const report = jobReport ?? latest.data?.report ?? null;
  const running = !!jobId && job.data?.status !== "done" && job.data?.status !== "failed";

  return (
    <div className="max-w-[1400px] mx-auto px-3 sm:px-5 lg:px-6 py-5 pb-24">
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-white">
            <FlaskConical className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">전략 실험</h1>
            <div className="text-sm text-slate-500 dark:text-slate-400">현재 운용 전략을 수집 데이터로 백테스트</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => latest.refetch()}
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800">
            <RefreshCcw className={`h-4 w-4 ${latest.isFetching ? "animate-spin" : ""}`} /> 새로고침
          </button>
          <button onClick={() => setShowForm((v) => !v)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-white hover:bg-primary-dark">
            <Play className="h-4 w-4" /> 새 실험
          </button>
        </div>
      </div>

      {showForm && (
        <div className="card mb-5 space-y-4 p-4">
          <div>
            <div className="mb-2 text-sm font-medium text-slate-700 dark:text-slate-200">전략 선택 <span className="text-xs text-slate-400">(미선택 시 기본 셋)</span></div>
            <div className="flex flex-wrap gap-2">
              {(catalog.data?.strategies ?? []).map((s) => (
                <label key={s.name} className="inline-flex items-center gap-1.5 rounded border border-slate-200 px-2 py-1 text-sm dark:border-slate-700">
                  <input type="checkbox" checked={!!selected[s.name]}
                    onChange={(e) => setSelected((p) => ({ ...p, [s.name]: e.target.checked }))} />
                  <span>{s.name}</span>
                  <span className="text-[10px] text-slate-400">{s.timeframe}</span>
                </label>
              ))}
              {catalog.isLoading && <span className="text-sm text-slate-400">전략 로딩...</span>}
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <label className="text-sm">
              <span className="text-slate-500">시작일</span>
              <input type="date" value={start} onChange={(e) => setStart(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900" />
            </label>
            <label className="text-sm">
              <span className="text-slate-500">종료일</span>
              <input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900" />
            </label>
            <label className="text-sm">
              <span className="text-slate-500">종목 (선택, 쉼표구분)</span>
              <input type="text" value={symbols} placeholder="005930, 000660" onChange={(e) => setSymbols(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 dark:border-slate-700 dark:bg-slate-900" />
            </label>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={launch} disabled={running || runMut.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50">
              {running || runMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
              실행
            </button>
            {running && (
              <>
                <span className="text-sm text-slate-500">실행 중... (백테스트는 수 분 걸릴 수 있습니다)</span>
                <HeuristicProgressBar startedAt={job.data?.started_at ?? job.data?.created_at} />
              </>
            )}
            {job.data?.status === "failed" && (
              <span className="inline-flex items-center gap-1 text-sm text-rose-600"><AlertCircle className="h-4 w-4" /> 실패: {job.data.error}</span>
            )}
            {job.data?.status === "done" && <span className="inline-flex items-center gap-1 text-sm text-emerald-600"><CheckCircle2 className="h-4 w-4" /> 완료</span>}
            {runMut.isError && <span className="text-sm text-rose-600">요청 실패: {String((runMut.error as Error)?.message)}</span>}
          </div>
        </div>
      )}

      {latest.isLoading && !report && <div className="card p-6 text-sm text-slate-500">불러오는 중...</div>}

      {report ? (
        <>
          {jobReport && (
            <div className="mb-3 inline-flex items-center gap-2 rounded bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
              <TrendingUp className="h-3.5 w-3.5" /> 방금 실행한 실험 결과
            </div>
          )}
          <ReportView report={report} />
        </>
      ) : (
        !latest.isLoading && (
          <div className="card flex flex-col items-center gap-2 p-10 text-center text-slate-500">
            <BarChart3 className="h-10 w-10 opacity-40" />
            <p className="text-sm">아직 실험 리포트가 없습니다.</p>
            <p className="text-xs">&quot;새 실험&quot;으로 현재 전략을 백테스트하거나, 야간 배치가 생성할 때까지 기다리세요.</p>
          </div>
        )
      )}
    </div>
  );
}
