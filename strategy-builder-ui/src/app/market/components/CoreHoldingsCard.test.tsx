import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  CoreHolding,
  PortfolioCoreLatest,
} from "@/lib/dashboard/portfolio";
import CoreHoldingsCard from "./CoreHoldingsCard";

// core_holdings.yaml 로더 계약 기본값 — weight/target/actual은 fraction.
function holding(overrides: Partial<CoreHolding> = {}): CoreHolding {
  return {
    symbol: "012450",
    name: "한화에어로스페이스",
    sector: "defense",
    sector_label: "방산",
    thesis: "방산 수출 구조적 성장",
    kill_criteria: ["수주 잔고 2분기 연속 감소", "수출 규제 재도입"],
    shares: 10,
    avg_price: 250_000,
    last_valuation: { date: "2026-07-01", price: 300_000 },
    valuation: 3_000_000,
    weight: 0.6,
    ...overrides,
  };
}

function latest(overrides: Partial<PortfolioCoreLatest> = {}): PortfolioCoreLatest {
  return {
    status: "ok",
    checked_at: "2026-07-03T10:00:00+00:00",
    source: "portfolio:tier3:watch",
    manual_track: true,
    tier3: null,
    holdings: [
      holding(),
      holding({
        symbol: "042700",
        name: "한미반도체",
        sector: "semis_equipment",
        sector_label: "반도체 장비",
        thesis: "HBM 장비 수요",
        kill_criteria: ["TC 본더 경쟁 심화"],
        shares: 20,
        avg_price: 100_000,
        last_valuation: null,
        valuation: 2_000_000,
        weight: 0.4,
      }),
    ],
    candidates: [
      {
        symbol: "277810",
        name: "레인보우로보틱스",
        sector: "robotics",
        sector_label: "로보틱스",
        thesis: "협동로봇 침투율 상승",
        kill_criteria: ["대기업 납품 계약 해지"],
      },
    ],
    sectors: {
      defense: { label: "방산", target_weight: 0.35, actual_weight: 0.6 },
      semis_equipment: {
        label: "반도체 장비",
        target_weight: 0.35,
        actual_weight: 0.4,
      },
      robotics: { label: "로보틱스", target_weight: 0.15, actual_weight: null },
      cash: { label: "현금", target_weight: 0.15, actual_weight: null },
    },
    rebalancing: { drift_threshold_pct: 0.1, single_holding_max: 0.25 },
    ...overrides,
  };
}

const EMPTY: PortfolioCoreLatest = {
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

describe("CoreHoldingsCard", () => {
  it("renders holdings with valuation, weight, and expandable kill criteria", () => {
    render(<CoreHoldingsCard data={latest()} isLoading={false} />);

    expect(screen.getByText("코어 홀딩스 — 트랙 A")).toBeInTheDocument();
    expect(screen.getByText("2종목")).toBeInTheDocument();
    // 보유 종목 행: 이름/코드/섹터 라벨/논거.
    expect(screen.getByText("한화에어로스페이스")).toBeInTheDocument();
    expect(screen.getByText("012450")).toBeInTheDocument();
    expect(screen.getByText("방산 수출 구조적 성장")).toBeInTheDocument();
    // 평가액 (₩ KRW) + 평가 기준일 / 평단 폴백.
    expect(screen.getByText(/₩3,000,000/)).toBeInTheDocument();
    expect(screen.getByText("2026-07-01 평가")).toBeInTheDocument();
    expect(screen.getByText(/₩2,000,000/)).toBeInTheDocument();
    expect(screen.getByText("평단 기준")).toBeInTheDocument();
    // 비중 fraction→% 변환 (0.6 → 60.0%).
    expect(screen.getByText("60.0%")).toBeInTheDocument();
    expect(screen.getByText("40.0%")).toBeInTheDocument();
    // Kill Criteria expandable — summary + 내용(details 내부에 존재).
    expect(screen.getByText("2개 보기")).toBeInTheDocument();
    expect(
      screen.getByText("수주 잔고 2분기 연속 감소"),
    ).toBeInTheDocument();
    expect(screen.getByText("수출 규제 재도입")).toBeInTheDocument();
  });

  it("marks a sector allocation drift beyond the threshold in amber", () => {
    render(<CoreHoldingsCard data={latest()} isLoading={false} />);

    // 방산: 실 60% vs 목표 35% → 드리프트 +25.0%p (임계 ±10%p 초과).
    const drift = screen.getByText("드리프트 +25.0%p");
    expect(drift.className).toContain("amber");
    // 반도체 장비: 실 40% vs 목표 35% → 임계 이내, 드리프트 배지 없음.
    expect(screen.queryByText("드리프트 +5.0%p")).not.toBeInTheDocument();
    // 실비중 미산출 섹터는 라벨로 표기된다.
    expect(screen.getAllByText(/실비중 미산출/).length).toBe(2);
    expect(screen.getByText(/드리프트 임계 ±10%p/)).toBeInTheDocument();
  });

  it("flags a holding over the single-holding cap with a label", () => {
    // 0.6 > 상한 0.5 > 0.4 — 초과 종목만 라벨이 붙는 것을 확인한다.
    render(
      <CoreHoldingsCard
        data={latest({
          rebalancing: { drift_threshold_pct: 0.1, single_holding_max: 0.5 },
        })}
        isLoading={false}
      />,
    );

    // 상한 초과는 amber + 텍스트 병기 (색상 단독 의미 전달 금지).
    expect(screen.getByText("단일 종목 상한 50% 초과")).toBeInTheDocument();
    expect(screen.getByText("60.0%").className).toContain("amber");
    expect(screen.getByText("40.0%").className).not.toContain("amber");
  });

  it("lists candidates with thesis and kill criteria", () => {
    render(<CoreHoldingsCard data={latest()} isLoading={false} />);

    expect(screen.getByText("후보 리스트")).toBeInTheDocument();
    expect(screen.getByText("레인보우로보틱스")).toBeInTheDocument();
    expect(screen.getByText("협동로봇 침투율 상승")).toBeInTheDocument();
    expect(screen.getByText("대기업 납품 계약 해지")).toBeInTheDocument();
  });

  it("renders the empty-ledger guidance when nothing is registered", () => {
    render(<CoreHoldingsCard data={EMPTY} isLoading={false} />);

    expect(screen.getByText(/보유 종목 미등록/)).toBeInTheDocument();
    expect(
      screen.getByText("config/portfolio/core_holdings.yaml"),
    ).toBeInTheDocument();
    expect(screen.getByText("sts portfolio")).toBeInTheDocument();
    expect(screen.getByText("후보 없음")).toBeInTheDocument();
    // 로더 미가동(sectors null) → 섹터 배분 섹션은 렌더링되지 않는다.
    expect(
      screen.queryByText("섹터 배분 — 실비중 vs 목표"),
    ).not.toBeInTheDocument();
  });

  it("always shows the manual-track label (자동 매매 없음)", () => {
    const { rerender } = render(
      <CoreHoldingsCard data={latest()} isLoading={false} />,
    );
    expect(screen.getByText("수동 트랙 — 자동 매매 없음")).toBeInTheDocument();

    rerender(<CoreHoldingsCard data={EMPTY} isLoading={false} />);
    expect(screen.getByText("수동 트랙 — 자동 매매 없음")).toBeInTheDocument();
  });

  it("exposes an accessible loading status while pending", () => {
    render(<CoreHoldingsCard data={undefined} isLoading />);

    expect(
      screen.getByRole("status", { name: "Loading core holdings" }),
    ).toBeInTheDocument();
  });
});
