import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { FeedbackListResponse } from "@/lib/dashboard/reports";
import FeedbackSummaryCard from "./FeedbackSummaryCard";

function weeklyList(): FeedbackListResponse {
  return {
    kind: "weekly",
    count: 2,
    reports: [
      {
        kind: "weekly",
        period_label: "2026-07-06",
        generated_at: "2026-07-06T18:10:00+09:00",
        tracks: {
          B: {
            trades: 12,
            win_rate: 0.58,
            avg_win_loss: 1.4,
            expectancy: 0.21,
            realized_pnl: 350000,
            slippage: null,
          },
          C: {
            trades: 5,
            win_rate: 40.0,
            avg_win_loss: 2.1,
            expectancy: -0.05,
            realized_pnl: -80000,
            slippage: 3.2,
          },
          A: {
            trades: null,
            win_rate: null,
            avg_win_loss: null,
            expectancy: null,
            realized_pnl: null,
            slippage: null,
          },
        },
        missing: [],
        headline: "주간 요약",
        md_exists: true,
      },
      {
        kind: "weekly",
        period_label: "2026-06-29",
        generated_at: "2026-06-29T18:10:00+09:00",
        tracks: {},
        missing: [],
        md_exists: true,
      },
    ],
  };
}

function monthlyList(): FeedbackListResponse {
  return {
    kind: "monthly",
    count: 1,
    reports: [
      {
        kind: "monthly",
        period_label: "2026-06",
        generated_at: "2026-07-01T09:00:00+09:00",
        tracks: {},
        missing: [],
        contribution: "6월 트랙 B 기여 +2.1%, 트랙 C -0.4%",
        md_exists: true,
      },
    ],
  };
}

function quarterlyList(
  verdicts: Record<"B" | "C" | "A", string>,
): FeedbackListResponse {
  return {
    kind: "quarterly",
    count: 1,
    reports: [
      {
        kind: "quarterly",
        period_label: "2026-Q2",
        generated_at: "2026-07-01T09:00:00+09:00",
        tracks: {},
        missing: [],
        verdicts,
        md_exists: true,
      },
    ],
  };
}

describe("FeedbackSummaryCard", () => {
  it("renders weekly track metrics, monthly contribution, and recent links", () => {
    render(
      <FeedbackSummaryCard
        weekly={weeklyList()}
        monthly={monthlyList()}
        quarterly={quarterlyList({ B: "met", C: "below", A: "deferred" })}
      />,
    );

    // Weekly track rows.
    expect(screen.getByText("B (주식)")).toBeInTheDocument();
    expect(screen.getByText("C (선물)")).toBeInTheDocument();
    // win_rate 0.58 fraction → 58.0%, 40.0 already percent → 40.0%.
    expect(screen.getByText("58.0%")).toBeInTheDocument();
    expect(screen.getByText("40.0%")).toBeInTheDocument();
    expect(screen.getByText("₩350,000")).toBeInTheDocument();
    expect(screen.getByText("₩-80,000")).toBeInTheDocument();

    // Monthly contribution one-liner.
    expect(
      screen.getByText(/6월 트랙 B 기여/),
    ).toBeInTheDocument();

    // Manual-decision disclaimer.
    expect(
      screen.getByText("판정 자료 — 승격/강등 결정은 수동"),
    ).toBeInTheDocument();

    // Recent report links point at the read-only JSON endpoint.
    const link = screen.getByRole("link", { name: "2026-07-06" });
    expect(link).toHaveAttribute(
      "href",
      "/api/reports/feedback/weekly/2026-07-06",
    );
  });

  it("renders empty state when no reports are available", () => {
    render(<FeedbackSummaryCard weekly={undefined} monthly={undefined} />);
    expect(
      screen.getByText("리포트 미생성 — 주간 배치 가동 후 표시"),
    ).toBeInTheDocument();
  });

  it("shows the loading empty state while fetching with no data", () => {
    render(<FeedbackSummaryCard isLoading />);
    expect(screen.getByText("리포트 불러오는 중…")).toBeInTheDocument();
  });

  it.each([
    ["met", "충족"],
    ["below", "미달"],
    ["insufficient", "자료부족"],
    ["deferred", "유예"],
  ])("renders the %s quarterly verdict badge as %s", (verdict, label) => {
    render(
      <FeedbackSummaryCard
        quarterly={quarterlyList({
          B: verdict,
          C: verdict,
          A: verdict,
        })}
      />,
    );
    // All three tracks share the verdict → the label appears three times.
    expect(screen.getAllByText(label)).toHaveLength(3);
  });

  it("falls back to N/A for an unrecognized verdict", () => {
    render(
      <FeedbackSummaryCard
        quarterly={quarterlyList({ B: "weird", C: "", A: "unknown" })}
      />,
    );
    expect(screen.getAllByText("N/A")).toHaveLength(3);
  });
});
