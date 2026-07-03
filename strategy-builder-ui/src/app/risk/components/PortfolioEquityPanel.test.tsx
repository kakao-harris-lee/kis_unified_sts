import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  PortfolioEquityLatest,
  PortfolioEquitySnapshot,
} from "@/lib/dashboard/portfolio";
import PortfolioEquityPanel from "./PortfolioEquityPanel";

// config/portfolio.yaml 기본 단계 미러 (설계서 §7.1).
const STAGES: NonNullable<PortfolioEquityLatest["stages"]> = {
  mode: "shadow",
  reduce: { threshold: -0.05, new_entry_size_factor: 0.5 },
  halt_new: { threshold: -0.08 },
  full_stop: { threshold: -0.12 },
};

function latest(
  overrides: Partial<PortfolioEquitySnapshot> = {},
  status: PortfolioEquityLatest["status"] = "ok",
): PortfolioEquityLatest {
  return {
    status,
    checked_at: "2026-07-03T10:00:00+00:00",
    source: "portfolio:equity:latest",
    equity: {
      total_equity: 125_000_000,
      track_a_equity: null,
      track_b_equity: 21_875_000,
      track_c_equity: 9_375_000,
      month_start_equity: 130_000_000,
      month_peak_equity: 131_500_000,
      // 배치 발행 단위는 비율(fraction) — 표시 시 -4.94%로 환산된다.
      monthly_mdd_pct: -0.0494,
      stage: "NORMAL",
      mode: "shadow",
      degraded: false,
      missing_components: [],
      asof: "2026-07-03T18:10:00+09:00",
      age_s: 120,
      stale: false,
      ...overrides,
    },
    stages: STAGES,
  };
}

describe("PortfolioEquityPanel", () => {
  it("renders total equity with track breakdown and missing track A", () => {
    render(<PortfolioEquityPanel data={latest()} isLoading={false} />);

    expect(screen.getByText("통합 자산")).toBeInTheDocument();
    expect(screen.getByText("₩125,000,000")).toBeInTheDocument();
    expect(screen.getByText("트랙 B (주식)")).toBeInTheDocument();
    expect(screen.getByText("₩21,875,000")).toBeInTheDocument();
    expect(screen.getByText("트랙 C (선물)")).toBeInTheDocument();
    expect(screen.getByText("₩9,375,000")).toBeInTheDocument();
    // 트랙 A 결측("" → null)은 명시적 미기록 표기.
    expect(screen.getByText("트랙 A (코어)")).toBeInTheDocument();
    expect(screen.getByText("미기록")).toBeInTheDocument();
    expect(screen.getByText("수동 원장")).toBeInTheDocument();
    // 월초/월중 최고 컨텍스트.
    expect(screen.getByText("₩130,000,000")).toBeInTheDocument();
    expect(screen.getByText("월중 최고 ₩131,500,000")).toBeInTheDocument();
    expect(screen.getByText(/KST/)).toBeInTheDocument();
  });

  it("renders track A value when the manual ledger is recorded", () => {
    render(
      <PortfolioEquityPanel
        data={latest({ track_a_equity: 93_750_000 })}
        isLoading={false}
      />,
    );

    expect(screen.getByText("₩93,750,000")).toBeInTheDocument();
    expect(screen.queryByText("미기록")).not.toBeInTheDocument();
  });

  it("emphasizes the negative monthly MDD and shows stage thresholds", () => {
    render(<PortfolioEquityPanel data={latest()} isLoading={false} />);

    const mdd = screen.getByText("-4.94%");
    expect(mdd.className).toContain("text-loss");
    expect(
      screen.getByText("단계 임계 -5% / -8% / -12%"),
    ).toBeInTheDocument();
  });

  it("shows the NORMAL stage badge in emerald with the shadow mode badge", () => {
    render(<PortfolioEquityPanel data={latest()} isLoading={false} />);

    const badge = screen.getByText("NORMAL — 정상");
    expect(badge.className).toContain("emerald");
    expect(screen.getByText("shadow — 미집행")).toBeInTheDocument();
  });

  it.each([
    ["REDUCE", "REDUCE — 신규 사이즈 50%", "amber"],
    ["HALT_NEW", "HALT_NEW — 신규 진입 중단", "orange"],
    ["FULL_STOP", "FULL_STOP — 전 시스템 정지", "rose"],
  ])("renders the %s stage badge with its tone", (stage, label, tone) => {
    render(
      <PortfolioEquityPanel data={latest({ stage })} isLoading={false} />,
    );

    const badge = screen.getByText(label);
    expect(badge.className).toContain(tone);
  });

  it("falls back to a muted badge when the stage is not computed", () => {
    render(
      <PortfolioEquityPanel data={latest({ stage: null })} isLoading={false} />,
    );

    expect(screen.getByText("단계 미산출")).toBeInTheDocument();
  });

  it("shows the enforce mode badge in red when the breaker enforces", () => {
    render(
      <PortfolioEquityPanel data={latest({ mode: "enforce" })} isLoading={false} />,
    );

    const badge = screen.getByText("enforce — 집행 중");
    expect(badge.className).toContain("rose");
    expect(screen.queryByText("shadow — 미집행")).not.toBeInTheDocument();
  });

  it("renders the batch-not-running empty state when unavailable", () => {
    render(
      <PortfolioEquityPanel
        data={{
          status: "unavailable",
          checked_at: "2026-07-03T10:00:00+00:00",
          source: "portfolio:equity:latest",
          equity: null,
          stages: STAGES,
        }}
        isLoading={false}
      />,
    );

    expect(screen.getByText(/통합 자산 배치 미가동/)).toBeInTheDocument();
    expect(screen.getByText("portfolio:equity:latest")).toBeInTheDocument();
    // 배치 미가동 시 카드/배지 대신 config mode 배지만 유지된다.
    expect(screen.queryByText("총자산")).not.toBeInTheDocument();
    expect(screen.getByText("shadow — 미집행")).toBeInTheDocument();
  });

  it("shows a DEGRADED alert with the missing components", () => {
    render(
      <PortfolioEquityPanel
        data={latest({
          degraded: true,
          missing_components: ["track_a_ledger", "futures_account"],
        })}
        isLoading={false}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("DEGRADED");
    expect(alert).toHaveTextContent("track_a_ledger, futures_account");
  });

  it("shows a stale alert when the publication is old", () => {
    render(
      <PortfolioEquityPanel data={latest({ stale: true })} isLoading={false} />,
    );

    expect(
      screen.getByText(/마지막 발행이 오래되었습니다/),
    ).toBeInTheDocument();
  });

  it("exposes an accessible loading status while pending", () => {
    render(<PortfolioEquityPanel data={undefined} isLoading />);

    expect(
      screen.getByRole("status", { name: "Loading unified equity" }),
    ).toBeInTheDocument();
  });
});
