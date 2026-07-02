import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  MarketRiskGateInfo,
  MarketRiskGateRule,
} from "@/lib/dashboard/marketRisk";
import TrackResponsePanel from "./TrackResponsePanel";

function rule(overrides: Partial<MarketRiskGateRule> = {}): MarketRiskGateRule {
  return {
    allow_long: true,
    allow_short: true,
    size_factor: 1.0,
    min_confidence: null,
    ...overrides,
  };
}

// config/market_risk_gate.yaml 기본 매트릭스 미러 (§4.2).
function gateInfo(
  overrides: Partial<MarketRiskGateInfo> = {},
): MarketRiskGateInfo {
  return {
    mode: "shadow",
    staleness_max_age_seconds: 21600,
    matrix: {
      stock: {
        LOW: rule(),
        NEUTRAL: rule(),
        ELEVATED: rule({ min_confidence: "HIGH" }),
        HIGH: rule({ allow_long: false }),
        CRITICAL: rule({ allow_long: false, allow_short: false }),
      },
      futures: {
        LOW: rule(),
        NEUTRAL: rule(),
        ELEVATED: rule({ size_factor: 0.7 }),
        HIGH: rule({ allow_long: false, size_factor: 0.5 }),
        CRITICAL: rule({ allow_long: false, allow_short: false }),
      },
    },
    ...overrides,
  };
}

describe("TrackResponsePanel", () => {
  it("renders the live matrix with the current band row highlighted", () => {
    render(<TrackResponsePanel band="HIGH" score={74.2} gate={gateInfo()} />);

    // shadow 모드 라벨은 라이브 전환 후에도 유지된다.
    expect(screen.getByText("shadow — 미집행")).toBeInTheDocument();
    expect(
      screen.getByText(/config\/market_risk_gate\.yaml 라이브 매트릭스/),
    ).toBeInTheDocument();

    const activeRow = document.querySelector('tr[aria-current="true"]');
    expect(activeRow).not.toBeNull();
    const active = within(activeRow as HTMLElement);
    expect(active.getByText("HIGH")).toBeInTheDocument();
    expect(active.getByText("현재")).toBeInTheDocument();
    // 현재 밴드 행의 각 트랙 지시 (stock HIGH / futures HIGH).
    expect(active.getByText("신규 롱 금지")).toBeInTheDocument();
    expect(active.getByText("신규 롱 금지 · 사이즈 50%")).toBeInTheDocument();
    // 트랙 A(수동) 지시는 정적 roadmap 정본을 유지한다.
    expect(active.getByText("신규 매수 중단")).toBeInTheDocument();

    // 다른 밴드 행도 매트릭스에 함께 표시된다 (ELEVATED).
    expect(screen.getByText("신뢰도 HIGH 이상만")).toBeInTheDocument();
    expect(screen.getByText("사이즈 70%")).toBeInTheDocument();
    expect(screen.getAllByText("신규 진입 전면 금지").length).toBe(2);
  });

  it("shows the enforce badge in red when the gate is enforcing", () => {
    render(
      <TrackResponsePanel
        band="CRITICAL"
        score={91.3}
        gate={gateInfo({ mode: "enforce" })}
      />,
    );

    expect(screen.getByText("enforce — 집행 중")).toBeInTheDocument();
    expect(screen.queryByText("shadow — 미집행")).not.toBeInTheDocument();
    expect(
      screen.getByText(/차단 규칙이 신규 진입에 실제 집행됩니다/),
    ).toBeInTheDocument();
  });

  it("shows the off badge when the gate is disabled", () => {
    render(
      <TrackResponsePanel band="LOW" score={12.0} gate={gateInfo({ mode: "off" })} />,
    );

    expect(screen.getByText("off — 비활성")).toBeInTheDocument();
    expect(screen.getByText(/게이트 비활성\(off\)/)).toBeInTheDocument();
  });

  it("renders the live matrix without a highlight when no band is computed", () => {
    render(<TrackResponsePanel band={null} score={null} gate={gateInfo()} />);

    expect(document.querySelector('tr[aria-current="true"]')).toBeNull();
    expect(screen.queryByText("현재")).not.toBeInTheDocument();
    expect(
      screen.getByText(/밴드가 산출되면 트랙별 지시가 표시됩니다/),
    ).toBeInTheDocument();
    // 매트릭스 자체는 전체 밴드가 그대로 표시된다.
    expect(screen.getAllByText("신규 진입 전면 금지").length).toBe(2);
  });

  it("falls back to the static roadmap matrix when the gate section is absent", () => {
    render(<TrackResponsePanel band="HIGH" score={74.2} gate={null} />);

    expect(screen.getByText("shadow — 미집행")).toBeInTheDocument();
    expect(
      screen.getByText("신규 롱 전면 금지 · 보유분 손절/청산 규칙만 가동"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Phase 2 enforcement 전까지 로그 전용/),
    ).toBeInTheDocument();
    expect(document.querySelector("table")).toBeNull();
  });

  it("keeps the empty-band fallback when neither gate nor band is available", () => {
    render(<TrackResponsePanel band={null} score={null} />);

    expect(screen.getByText("밴드 미산출 — 매트릭스 대기 중")).toBeInTheDocument();
  });
});
