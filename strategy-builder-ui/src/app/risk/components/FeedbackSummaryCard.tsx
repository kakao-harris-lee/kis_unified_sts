"use client";

import { useState } from "react";
import { ClipboardList, FileText, Info } from "lucide-react";
import { formatKstDateTime } from "@/lib/dashboard/format";
import type {
  FeedbackListResponse,
  FeedbackReportRow,
  FeedbackTrackMetrics,
} from "@/lib/dashboard/reports";
import {
  VERDICT_SPECS,
  normalizeVerdict,
  reportsApi,
} from "@/lib/dashboard/reports";

// 성과 피드백 요약 카드 (Phase 6B — roadmap §Phase 6, 설계서 §8). 주간/월간/
// 분기 리포트 파일을 읽기 전용으로 요약한다. 분기 판정은 "판정 자료"일 뿐,
// 승격/강등 결정은 수동이라는 게 이 시스템의 계약이다. 데이터 부재 시
// empty state — 엔진 미가동에도 /risk 페이지는 정상 렌더된다.

const RECENT_LINK_COUNT = 5;

// 리포트 본문은 인증이 필요한 /api/reports/feedback/{kind}/{period} 에서만 온다.
// 예전에는 평범한 <a href> 였는데, 브라우저 내비게이션은 X-API-Key 헤더를 실을
// 수 없어서 **UI 프록시가 인증을 안 하던 동안에만** 열렸다(#861 리뷰 노트 f).
// 프록시가 이제 키를 요구하므로, 링크 대신 인증된 클라이언트로 받아 JSON 파일로
// 내려준다 — 같은 읽기 전용 자료, 무인증 경로 0.
async function downloadFeedbackReport(periodLabel: string): Promise<void> {
  const { data } = await reportsApi.getFeedbackReport("weekly", periodLabel);
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `feedback-weekly-${periodLabel}.json`;
    anchor.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}

function fmtWinRate(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  // 리포트는 승률을 비율(0.58) 또는 퍼센트(58.0)로 발행할 수 있다 —
  // 관대하게 환산한다(≤1 이면 비율로 간주).
  const pct = Math.abs(v) <= 1 ? v * 100 : v;
  return `${pct.toFixed(1)}%`;
}

function fmtEv(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return v.toFixed(2);
}

function fmtKrw(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `₩${Math.round(v).toLocaleString("ko-KR")}`;
}

function pnlClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return "text-slate-500";
  return v >= 0 ? "text-profit" : "text-loss";
}

const EMPTY_METRICS: FeedbackTrackMetrics = {
  trades: null,
  win_rate: null,
  avg_win_loss: null,
  expectancy: null,
  realized_pnl: null,
  slippage: null,
};

function TrackRow({
  label,
  metrics,
}: {
  label: string;
  metrics: FeedbackTrackMetrics;
}) {
  return (
    <tr className="border-t border-slate-100 dark:border-slate-800">
      <td className="py-2 pr-3 text-left font-medium text-slate-700 dark:text-slate-200">
        {label}
      </td>
      <td className="py-2 px-3 text-right tabular-nums">
        {metrics.trades ?? "-"}
      </td>
      <td className="py-2 px-3 text-right tabular-nums">
        {fmtWinRate(metrics.win_rate)}
      </td>
      <td className="py-2 px-3 text-right tabular-nums">
        {fmtEv(metrics.expectancy)}
      </td>
      <td
        className={`py-2 pl-3 text-right tabular-nums font-semibold ${pnlClass(metrics.realized_pnl)}`}
      >
        {fmtKrw(metrics.realized_pnl)}
      </td>
    </tr>
  );
}

function VerdictBadge({
  track,
  raw,
}: {
  track: string;
  raw: string | null | undefined;
}) {
  const spec = VERDICT_SPECS[normalizeVerdict(raw)];
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {track}
      </span>
      <span
        className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-bold ${spec.className}`}
      >
        {spec.label}
      </span>
    </div>
  );
}

export interface FeedbackSummaryCardProps {
  weekly?: FeedbackListResponse;
  monthly?: FeedbackListResponse;
  quarterly?: FeedbackListResponse;
  isLoading?: boolean;
}

export default function FeedbackSummaryCard({
  weekly,
  monthly,
  quarterly,
  isLoading = false,
}: FeedbackSummaryCardProps) {
  // 다운로드 실패를 조용히 삼키지 않는다 — 빈 상태로 보이면 리포트가 없는 것과
  // 구분이 안 된다(#469 의 catch {} 전례).
  const [downloading, setDownloading] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleDownload = async (periodLabel: string): Promise<void> => {
    setDownloading(periodLabel);
    setDownloadError(null);
    try {
      await downloadFeedbackReport(periodLabel);
    } catch {
      setDownloadError(`${periodLabel} 리포트를 불러오지 못했습니다`);
    } finally {
      setDownloading(null);
    }
  };

  const latestWeekly: FeedbackReportRow | undefined = weekly?.reports?.[0];
  const latestMonthly: FeedbackReportRow | undefined = monthly?.reports?.[0];
  const latestQuarterly: FeedbackReportRow | undefined = quarterly?.reports?.[0];

  const hasAny =
    Boolean(latestWeekly) ||
    Boolean(latestMonthly) ||
    Boolean(latestQuarterly);

  return (
    <section
      aria-labelledby="feedback-summary-heading"
      className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ClipboardList
            className="h-4 w-4 text-slate-500"
            aria-hidden="true"
          />
          <h2
            id="feedback-summary-heading"
            className="text-lg font-semibold text-slate-900 dark:text-slate-100"
          >
            성과 피드백
          </h2>
        </div>
        {latestWeekly ? (
          <span className="text-xs text-slate-500 dark:text-slate-400">
            주간 {latestWeekly.period_label} ·{" "}
            {formatKstDateTime(latestWeekly.generated_at, "-")}
          </span>
        ) : null}
      </div>

      {!hasAny ? (
        <div
          className="mt-3 rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-800/40 dark:text-slate-400"
          data-testid="feedback-empty"
        >
          {isLoading
            ? "리포트 불러오는 중…"
            : "리포트 미생성 — 주간 배치 가동 후 표시"}
        </div>
      ) : (
        <div className="mt-3 space-y-4">
          {/* 최신 주간 — 트랙 B/C 승률·EV·실현 PnL */}
          {latestWeekly ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <caption className="sr-only">
                  최신 주간 리포트 트랙별 승률·기대값·실현 손익
                </caption>
                <thead>
                  <tr className="text-xs text-slate-500 dark:text-slate-400">
                    <th scope="col" className="py-1 pr-3 text-left font-medium">
                      트랙
                    </th>
                    <th scope="col" className="py-1 px-3 text-right font-medium">
                      거래
                    </th>
                    <th scope="col" className="py-1 px-3 text-right font-medium">
                      승률
                    </th>
                    <th scope="col" className="py-1 px-3 text-right font-medium">
                      EV
                    </th>
                    <th scope="col" className="py-1 pl-3 text-right font-medium">
                      실현 PnL
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <TrackRow
                    label="B (주식)"
                    metrics={latestWeekly.tracks?.B ?? EMPTY_METRICS}
                  />
                  <TrackRow
                    label="C (선물)"
                    metrics={latestWeekly.tracks?.C ?? EMPTY_METRICS}
                  />
                </tbody>
              </table>
            </div>
          ) : null}

          {/* 최신 월간 기여도 한 줄 */}
          {latestMonthly ? (
            <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:bg-slate-800/50 dark:text-slate-300">
              <span className="font-medium text-slate-500 dark:text-slate-400">
                월간 {latestMonthly.period_label}
              </span>
              {" · "}
              {latestMonthly.contribution ??
                latestMonthly.headline ??
                "기여도 요약 없음"}
            </div>
          ) : null}

          {/* 분기 판정 배지 — 판정 자료 (승격/강등 수동) */}
          {latestQuarterly ? (
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                  분기 {latestQuarterly.period_label} 판정
                </span>
                <VerdictBadge
                  track="B"
                  raw={latestQuarterly.verdicts?.B}
                />
                <VerdictBadge
                  track="C"
                  raw={latestQuarterly.verdicts?.C}
                />
                <VerdictBadge
                  track="A"
                  raw={latestQuarterly.verdicts?.A}
                />
              </div>
              <p className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500">
                <Info className="h-3 w-3 shrink-0" aria-hidden="true" />
                판정 자료 — 승격/강등 결정은 수동
              </p>
            </div>
          ) : null}

          {/* 최근 주간 리포트 링크 */}
          {weekly?.reports?.length ? (
            <div className="border-t border-slate-100 pt-3 dark:border-slate-800">
              <div className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400">
                <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                최근 리포트
              </div>
              <ul className="flex flex-wrap gap-2">
                {weekly.reports.slice(0, RECENT_LINK_COUNT).map((row) => (
                  <li key={row.period_label}>
                    <button
                      type="button"
                      onClick={() => void handleDownload(row.period_label)}
                      disabled={downloading === row.period_label}
                      className="inline-flex items-center rounded border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600 transition hover:bg-slate-50 focus-ring disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                    >
                      {row.period_label}
                    </button>
                  </li>
                ))}
              </ul>
              {downloadError ? (
                <p role="alert" className="mt-1.5 text-xs text-loss">
                  {downloadError}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
