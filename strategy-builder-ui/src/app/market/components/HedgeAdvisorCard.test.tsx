import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  PortfolioHedgeHistory,
  PortfolioHedgeLatest,
  PortfolioHedgeSnapshot,
} from "@/lib/dashboard/portfolio";
import HedgeAdvisorCard from "./HedgeAdvisorCard";

// portfolio:hedge:latest 계약 기본값 (미니 KOSPI200 — O4). 명목/노출은 KRW,
// futures_net_notional은 서명(숏 음수).
function snapshot(
  overrides: Partial<PortfolioHedgeSnapshot> = {},
): PortfolioHedgeSnapshot {
  return {
    product: "mini_kospi200",
    multiplier: 50_000,
    futures_price: 368.5,
    stock_long_notional: 52_000_000,
    portfolio_beta: 1.08,
    beta_notional: 56_160_000,
    futures_net_contracts: -1,
    futures_net_notional: -18_425_000,
    net_beta_exposure: 37_735_000,
    recommended_short_contracts: 3,
    residual_exposure_after: -13_520_000,
    band: "HIGH",
    score: 74.2,
    advisory_active: true,
    reason: "HIGH 밴드 + 순 β-노출이 헤지 임계 초과",
    degraded: false,
    missing_components: [],
    asof: "2026-07-03T18:40:00+09:00",
    age_s: 120,
    stale: false,
    ...overrides,
  };
}

function latest(
  overrides: Partial<PortfolioHedgeSnapshot> = {},
  status: PortfolioHedgeLatest["status"] = "ok",
): PortfolioHedgeLatest {
  return {
    status,
    checked_at: "2026-07-03T10:00:00+00:00",
    source: "portfolio:hedge:latest",
    advisory_only: true,
    hedge: snapshot(overrides),
  };
}

const UNAVAILABLE: PortfolioHedgeLatest = {
  status: "unavailable",
  checked_at: "2026-07-03T10:00:00+00:00",
  source: "portfolio:hedge:latest",
  advisory_only: true,
  hedge: null,
};

const EMPTY_HISTORY: PortfolioHedgeHistory = {
  status: "empty",
  days: 30,
  start: "2026-06-03",
  end: "2026-07-03",
  count: 0,
  points: [],
};

const HISTORY: PortfolioHedgeHistory = {
  status: "ok",
  days: 30,
  start: "2026-06-03",
  end: "2026-07-03",
  count: 2,
  points: [
    {
      asof: "2026-07-01T18:40:00+09:00",
      trade_date: "2026-07-01",
      recommended_short_contracts: 2,
      net_beta_exposure: 31_000_000,
      beta_notional: 50_000_000,
      futures_net_notional: -19_000_000,
      residual_exposure_after: -5_800_000,
      futures_price: 366.0,
      score: 71.5,
      product: "mini_kospi200",
      band: "HIGH",
      reason: "HIGH 밴드",
      advisory_active: true,
    },
    {
      asof: "2026-07-02T18:40:00+09:00",
      trade_date: "2026-07-02",
      recommended_short_contracts: 3,
      net_beta_exposure: 37_735_000,
      beta_notional: 56_160_000,
      futures_net_notional: -18_425_000,
      residual_exposure_after: -13_520_000,
      futures_price: 368.5,
      score: 74.2,
      product: "mini_kospi200",
      band: "CRITICAL",
      reason: "CRITICAL 밴드",
      advisory_active: true,
    },
  ],
};

describe("HedgeAdvisorCard", () => {
  it("renders exposures, recommendation, and reason when advisory is active", () => {
    render(
      <HedgeAdvisorCard
        data={latest()}
        history={EMPTY_HISTORY}
        isLoading={false}
      />,
    );

    expect(screen.getByText("헤지 어드바이저")).toBeInTheDocument();
    // 밴드색 강조 배지 (HIGH → orange 톤).
    const badge = screen.getByText("헤지 검토 권고");
    expect(badge.className).toContain("orange");
    // 현물 롱 명목가 + β + β-노출 sub.
    expect(screen.getByText("₩52,000,000")).toBeInTheDocument();
    expect(
      screen.getByText("포트폴리오 β 1.08 → β-노출 ₩56,160,000"),
    ).toBeInTheDocument();
    // 선물 넷 (서명 계약수 + 서명 명목).
    expect(screen.getByText("-1계약")).toBeInTheDocument();
    expect(
      screen.getByText("₩-18,425,000 (서명 · 숏 음수)"),
    ).toBeInTheDocument();
    // 순 β-노출.
    expect(screen.getByText("₩37,735,000")).toBeInTheDocument();
    // 권고: 미니 KOSPI200 숏 N계약 + 잔여 노출 병기 + 근거.
    expect(
      screen.getByText(/미니 KOSPI200 숏 3계약 검토/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/실행 시 잔여 노출 ₩-13,520,000/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("근거: HIGH 밴드 + 순 β-노출이 헤지 임계 초과"),
    ).toBeInTheDocument();
    // 메타: product·승수·선물가·asof.
    expect(
      screen.getByText(/미니 KOSPI200 · 승수 ₩50,000\/pt · 선물가 368\.50/),
    ).toBeInTheDocument();
    expect(screen.getByText(/KST/)).toBeInTheDocument();
  });

  it("always shows the advisory-only label (자동 주문 없음)", () => {
    const { rerender } = render(
      <HedgeAdvisorCard
        data={latest()}
        history={EMPTY_HISTORY}
        isLoading={false}
      />,
    );
    expect(
      screen.getByText("권고 전용 — 자동 주문 없음"),
    ).toBeInTheDocument();

    rerender(
      <HedgeAdvisorCard
        data={UNAVAILABLE}
        history={EMPTY_HISTORY}
        isLoading={false}
      />,
    );
    expect(
      screen.getByText("권고 전용 — 자동 주문 없음"),
    ).toBeInTheDocument();
  });

  it("uses the band tone for the advisory badge (CRITICAL → rose)", () => {
    render(
      <HedgeAdvisorCard
        data={latest({ band: "CRITICAL" })}
        history={EMPTY_HISTORY}
        isLoading={false}
      />,
    );

    expect(screen.getByText("헤지 검토 권고").className).toContain("rose");
  });

  it("shows the muted no-advisory badge when advisory is inactive", () => {
    render(
      <HedgeAdvisorCard
        data={latest({
          advisory_active: false,
          recommended_short_contracts: 0,
          band: "NEUTRAL",
        })}
        history={EMPTY_HISTORY}
        isLoading={false}
      />,
    );

    expect(screen.getByText("권고 없음")).toBeInTheDocument();
    expect(screen.queryByText("헤지 검토 권고")).not.toBeInTheDocument();
    // 권고 계약수 0 → 권고 없음 문구 (숏 0계약을 표시하지 않는다).
    expect(screen.getByText("권고 계약수 없음")).toBeInTheDocument();
    expect(screen.queryByText(/숏 0계약/)).not.toBeInTheDocument();
  });

  it("renders the advisor-not-running empty state when unavailable", () => {
    render(
      <HedgeAdvisorCard
        data={UNAVAILABLE}
        history={EMPTY_HISTORY}
        isLoading={false}
      />,
    );

    expect(screen.getByText(/헤지 어드바이저 미가동/)).toBeInTheDocument();
    expect(screen.getByText("portfolio:hedge:latest")).toBeInTheDocument();
    expect(screen.getByText("권고 없음")).toBeInTheDocument();
    // 스냅샷 타일은 렌더링되지 않는다.
    expect(screen.queryByText("현물 롱 명목가")).not.toBeInTheDocument();
    // 이력 empty state.
    expect(
      screen.getByText(/권고 이력 없음 — 어드바이저 가동 후 축적됩니다/),
    ).toBeInTheDocument();
  });

  it("shows a DEGRADED alert with the missing components", () => {
    render(
      <HedgeAdvisorCard
        data={latest({
          degraded: true,
          missing_components: ["portfolio_beta", "futures_price"],
        })}
        history={EMPTY_HISTORY}
        isLoading={false}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("DEGRADED");
    expect(alert).toHaveTextContent("portfolio_beta, futures_price");
  });

  it("shows a stale alert when the advice is old", () => {
    render(
      <HedgeAdvisorCard
        data={latest({ stale: true })}
        history={EMPTY_HISTORY}
        isLoading={false}
      />,
    );

    expect(
      screen.getByText(/마지막 권고 산출이 오래되었습니다/),
    ).toBeInTheDocument();
  });

  it("lists recent advice newest-first with date, contracts, and band", () => {
    render(
      <HedgeAdvisorCard data={latest()} history={HISTORY} isLoading={false} />,
    );

    expect(screen.getByText("최근 권고 이력")).toBeInTheDocument();
    expect(screen.getByText(/최근 30일 · 2건/)).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    // 최근(07-02, CRITICAL) 권고가 먼저 온다.
    expect(items[0]).toHaveTextContent("2026-07-02");
    expect(items[0]).toHaveTextContent("숏 3계약");
    expect(items[0]).toHaveTextContent("CRITICAL");
    expect(items[1]).toHaveTextContent("2026-07-01");
    expect(items[1]).toHaveTextContent("숏 2계약");
    expect(items[1]).toHaveTextContent("HIGH");
  });

  it("exposes an accessible loading status while pending", () => {
    render(
      <HedgeAdvisorCard data={undefined} history={undefined} isLoading />,
    );

    expect(
      screen.getByRole("status", { name: "Loading hedge advisor" }),
    ).toBeInTheDocument();
  });
});
