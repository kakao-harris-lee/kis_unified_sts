import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  PortfolioCoreLatest,
  Tier3WatchSnapshot,
} from "@/lib/dashboard/portfolio";
import Tier3WatchCard from "./Tier3WatchCard";

// portfolio:tier3:watch 계약 기본값 — drawdown/trigger_threshold는 fraction
// (−0.16 = −16%, Phase 3 단위 컨벤션). 표시할 때만 ×100 변환된다.
function tier3(overrides: Partial<Tier3WatchSnapshot> = {}): Tier3WatchSnapshot {
  return {
    kospi_close: 2585.5,
    kospi_peak: 2810.32,
    drawdown: -0.08,
    trigger_threshold: -0.15,
    triggered: false,
    asof: "2026-07-03T18:40:00+09:00",
    age_s: 120,
    stale: false,
    ...overrides,
  };
}

function latest(
  overrides: Partial<Tier3WatchSnapshot> = {},
  status: PortfolioCoreLatest["status"] = "ok",
): PortfolioCoreLatest {
  return {
    status,
    checked_at: "2026-07-03T10:00:00+00:00",
    source: "portfolio:tier3:watch",
    manual_track: true,
    tier3: tier3(overrides),
    holdings: [],
    candidates: [],
    sectors: null,
    rebalancing: null,
  };
}

const UNAVAILABLE: PortfolioCoreLatest = {
  status: "unavailable",
  checked_at: "2026-07-03T10:00:00+00:00",
  source: "portfolio:tier3:watch",
  manual_track: true,
  tier3: null,
  holdings: [],
  candidates: [],
  sectors: null,
  rebalancing: null,
};

describe("Tier3WatchCard", () => {
  it("renders the drawdown gauge with fraction→% conversion and trigger line", () => {
    render(<Tier3WatchCard data={latest()} isLoading={false} />);

    expect(screen.getByText("Tier 3 워치")).toBeInTheDocument();
    // fraction −0.08 → −8.0% (게이지 aria + 헤드라인 수치).
    expect(
      screen.getByRole("img", {
        name: "KOSPI 고점 대비 드로다운 -8.0%, 트리거 -15.0% — 미발동",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("-8.0%")).toBeInTheDocument();
    // KOSPI 현재가/피크 타일.
    expect(screen.getByText("2,585.50")).toBeInTheDocument();
    expect(screen.getByText("2,810.32")).toBeInTheDocument();
    // 트리거 라인 설명 + 축 눈금 (0 ~ −25% 스케일).
    expect(screen.getByText(/▎트리거 -15\.0%/)).toBeInTheDocument();
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("-25%")).toBeInTheDocument();
  });

  it("shows the muted badge when not triggered", () => {
    render(<Tier3WatchCard data={latest()} isLoading={false} />);

    const badge = screen.getByText("미발동");
    expect(badge.className).toContain("slate");
    expect(
      screen.queryByText("Tier 3 발동 감시 — 분할 매수 검토는 수동"),
    ).not.toBeInTheDocument();
  });

  it("shows the rose emphasis badge and drawdown tone when triggered", () => {
    render(
      <Tier3WatchCard
        data={latest({ drawdown: -0.16, triggered: true })}
        isLoading={false}
      />,
    );

    const badge = screen.getByText("Tier 3 발동 감시 — 분할 매수 검토는 수동");
    expect(badge.className).toContain("rose");
    expect(screen.queryByText("미발동")).not.toBeInTheDocument();
    // 발동 상태는 게이지 aria에도 라벨로 실린다 (색상 단독 전달 금지).
    expect(
      screen.getByRole("img", {
        name: "KOSPI 고점 대비 드로다운 -16.0%, 트리거 -15.0% — 발동",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("-16.0%").className).toContain("rose");
  });

  it("always shows the manual-track label (자동 매매 없음)", () => {
    const { rerender } = render(
      <Tier3WatchCard data={latest()} isLoading={false} />,
    );
    expect(screen.getByText("수동 트랙 — 자동 매매 없음")).toBeInTheDocument();

    rerender(<Tier3WatchCard data={UNAVAILABLE} isLoading={false} />);
    expect(screen.getByText("수동 트랙 — 자동 매매 없음")).toBeInTheDocument();
  });

  it("renders the watch-not-running empty state when the key is absent", () => {
    render(<Tier3WatchCard data={UNAVAILABLE} isLoading={false} />);

    expect(screen.getByText(/Tier 3 워치 미가동/)).toBeInTheDocument();
    expect(screen.getByText("portfolio:tier3:watch")).toBeInTheDocument();
    // 게이지/타일은 렌더링되지 않는다.
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByText("KOSPI 종가")).not.toBeInTheDocument();
  });

  it("shows a stale alert when the watch publication is old", () => {
    render(
      <Tier3WatchCard data={latest({ stale: true })} isLoading={false} />,
    );

    expect(
      screen.getByText(/마지막 워치 산출이 오래되었습니다/),
    ).toBeInTheDocument();
  });

  it("exposes an accessible loading status while pending", () => {
    render(<Tier3WatchCard data={undefined} isLoading />);

    expect(
      screen.getByRole("status", { name: "Loading tier 3 watch" }),
    ).toBeInTheDocument();
  });
});
