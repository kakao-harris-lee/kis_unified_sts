import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import type { AxiosResponse } from "axios";

import MarketPage from "./page";
import { marketRiskApi, portfolioApi } from "@/lib/dashboard/api";
import type {
  MarketRiskHistory,
  MarketRiskLatest,
} from "@/lib/dashboard/marketRisk";
import type {
  PortfolioHedgeHistory,
  PortfolioHedgeLatest,
} from "@/lib/dashboard/portfolio";

vi.mock("@/components/dashboard/HeaderBar", () => ({
  default: () => <header aria-label="Cockpit header">KIS Cockpit</header>,
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div data-testid="responsive-chart">{children}</div>
  ),
  ComposedChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Line: () => null,
  Bar: ({ children }: { children?: ReactNode }) => <div>{children}</div>,
  Cell: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  ReferenceLine: () => null,
}));

vi.mock("@/lib/dashboard/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/dashboard/api")>(
    "@/lib/dashboard/api",
  );
  return {
    ...actual,
    marketRiskApi: { getLatest: vi.fn(), getHistory: vi.fn() },
    portfolioApi: {
      ...actual.portfolioApi,
      getHedge: vi.fn(),
      getHedgeHistory: vi.fn(),
    },
  };
});

function renderWithQueryClient(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

function axiosResponse<T>(data: T): AxiosResponse<T> {
  return {
    data,
    status: 200,
    statusText: "OK",
    headers: {},
    config: { headers: {} } as AxiosResponse<T>["config"],
  };
}

const NULL_COMPONENT = {
  sub: null,
  weight: null,
  contribution: null,
  raw: null,
  asof: null,
};

function latestPayload(
  overrides: Partial<NonNullable<MarketRiskLatest["risk"]>> = {},
  status: MarketRiskLatest["status"] = "ok",
): MarketRiskLatest {
  return {
    status,
    checked_at: "2026-07-02T10:00:00+00:00",
    source: "market:risk:latest",
    risk: {
      score: 74.2,
      score_ema3: 71.8,
      band: "HIGH",
      regime: "RISK_OFF",
      degraded: false,
      coverage_ratio: 0.875,
      missing_components: ["vol"],
      kind: "close",
      asof: "2026-07-02T18:40:00+09:00",
      age_s: 120,
      stale: false,
      score_delta_1d: 4.2,
      prev_close_score: 70.0,
      prev_close_date: "2026-07-01",
      components: {
        foreign_fut: {
          sub: 82,
          weight: 25,
          contribution: 22.4,
          raw: -18250,
          asof: "2026-07-02T18:40:00+09:00",
        },
        basis: {
          sub: 61,
          weight: 15,
          contribution: 10.0,
          raw: -0.42,
          asof: "2026-07-02T18:40:00+09:00",
        },
        usdkrw: NULL_COMPONENT,
        program: NULL_COMPONENT,
        oi: NULL_COMPONENT,
        overseas: NULL_COMPONENT,
        vol: NULL_COMPONENT,
        trend: NULL_COMPONENT,
      },
      ...overrides,
    },
    structure: {
      status: "ok",
      snapshot: "close",
      trade_date: "2026-07-02",
      asof: "2026-07-02T18:40:00+09:00",
      age_s: 300,
      coverage_ratio: 0.875,
      missing_components: [],
    },
    night_close: {
      available: true,
      status: "ok",
      close: 370.15,
      mrkt_basis: -0.85,
      dprt: -0.23,
      open_interest: 284500,
      acml_vol: 10250,
      product_code: "101W09",
      asof: "2026-07-02T06:00:00+09:00",
      age_s: 3600,
    },
  };
}

const EMPTY_HISTORY: MarketRiskHistory = {
  status: "empty",
  days: 90,
  start: "2026-04-03",
  end: "2026-07-02",
  count: 0,
  points: [],
};

// 헤지 어드바이저(Phase 4B)는 스모크에서 미가동(unavailable) 기본값 — 카드
// empty state가 페이지를 깨지 않고 렌더링되는 것까지가 스모크 범위다.
const HEDGE_UNAVAILABLE: PortfolioHedgeLatest = {
  status: "unavailable",
  checked_at: "2026-07-02T10:00:00+00:00",
  source: "portfolio:hedge:latest",
  advisory_only: true,
  hedge: null,
};

const EMPTY_HEDGE_HISTORY: PortfolioHedgeHistory = {
  status: "empty",
  days: 30,
  start: "2026-06-02",
  end: "2026-07-02",
  count: 0,
  points: [],
};

const GATE_RULE = {
  allow_long: true,
  allow_short: true,
  size_factor: 1.0,
  min_confidence: null,
};

// config/market_risk_gate.yaml 기본 매트릭스 미러 (Phase 2E gate 섹션).
const GATE_INFO: NonNullable<MarketRiskLatest["gate"]> = {
  mode: "shadow",
  staleness_max_age_seconds: 21600,
  matrix: {
    stock: {
      LOW: GATE_RULE,
      NEUTRAL: GATE_RULE,
      ELEVATED: { ...GATE_RULE, min_confidence: "HIGH" },
      HIGH: { ...GATE_RULE, allow_long: false },
      CRITICAL: { ...GATE_RULE, allow_long: false, allow_short: false },
    },
    futures: {
      LOW: GATE_RULE,
      NEUTRAL: GATE_RULE,
      ELEVATED: { ...GATE_RULE, size_factor: 0.7 },
      HIGH: { ...GATE_RULE, allow_long: false, size_factor: 0.5 },
      CRITICAL: { ...GATE_RULE, allow_long: false, allow_short: false },
    },
  },
};

describe("/market page smoke coverage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(marketRiskApi.getHistory).mockResolvedValue(
      axiosResponse(EMPTY_HISTORY),
    );
    vi.mocked(portfolioApi.getHedge).mockResolvedValue(
      axiosResponse(HEDGE_UNAVAILABLE),
    );
    vi.mocked(portfolioApi.getHedgeHistory).mockResolvedValue(
      axiosResponse(EMPTY_HEDGE_HISTORY),
    );
  });

  it("renders score header, breakdown table, and shadow track panel", async () => {
    vi.mocked(marketRiskApi.getLatest).mockResolvedValue(
      axiosResponse(latestPayload()),
    );

    renderWithQueryClient(<MarketPage />);

    expect(
      await screen.findByRole("heading", { name: "Market Risk & Structure" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("74.2")).toBeInTheDocument();
    expect(screen.getAllByText("HIGH").length).toBeGreaterThan(0);
    expect(screen.getByText("RISK_OFF")).toBeInTheDocument();
    expect(screen.getByText("Δ +4.2")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Refresh market risk" }),
    ).toBeInTheDocument();

    // 구성요소 분해: 라벨 + missing 표기가 함께 렌더링된다.
    expect(screen.getByText("외국인 선물 수급")).toBeInTheDocument();
    expect(screen.getByText("베이시스")).toBeInTheDocument();
    expect(screen.getAllByText("missing").length).toBeGreaterThan(0);

    // gate 섹션 부재 → 트랙 반응 패널은 정적 매트릭스로 폴백한다.
    expect(screen.getByText("shadow — 미집행")).toBeInTheDocument();
    expect(
      screen.getByText("신규 롱 전면 금지 · 보유분 손절/청산 규칙만 가동"),
    ).toBeInTheDocument();

    // 야간 신호 타일
    expect(screen.getByText("야간 K200 종가")).toBeInTheDocument();
    expect(screen.getByText("370.15")).toBeInTheDocument();

    // 헤지 카드 (Phase 4B) — 어드바이저 미가동 empty state에서도 카드와
    // 권고 전용 라벨은 항상 렌더링된다.
    expect(screen.getByText("헤지 어드바이저")).toBeInTheDocument();
    expect(screen.getByText("권고 전용 — 자동 주문 없음")).toBeInTheDocument();
    expect(screen.getByText(/헤지 어드바이저 미가동/)).toBeInTheDocument();
  });

  it("renders the live track matrix when the gate section is present", async () => {
    const payload = latestPayload();
    vi.mocked(marketRiskApi.getLatest).mockResolvedValue(
      axiosResponse({ ...payload, gate: GATE_INFO }),
    );

    renderWithQueryClient(<MarketPage />);

    // 라이브 매트릭스: 현재 밴드(HIGH) 행 강조 + 트랙별 라이브 지시.
    expect(await screen.findByText("신규 롱 금지 · 사이즈 50%")).toBeInTheDocument();
    expect(screen.getByText("shadow — 미집행")).toBeInTheDocument();
    expect(screen.getByText("현재")).toBeInTheDocument();
    expect(
      screen.queryByText("신규 롱 전면 금지 · 보유분 손절/청산 규칙만 가동"),
    ).not.toBeInTheDocument();
  });

  it("shows the enforce badge when the gate mode is enforce", async () => {
    const payload = latestPayload();
    vi.mocked(marketRiskApi.getLatest).mockResolvedValue(
      axiosResponse({ ...payload, gate: { ...GATE_INFO, mode: "enforce" } }),
    );

    renderWithQueryClient(<MarketPage />);

    expect(await screen.findByText("enforce — 집행 중")).toBeInTheDocument();
    expect(screen.queryByText("shadow — 미집행")).not.toBeInTheDocument();
  });

  it("shows the DEGRADED banner with coverage and missing components", async () => {
    vi.mocked(marketRiskApi.getLatest).mockResolvedValue(
      axiosResponse(latestPayload({ degraded: true }, "degraded")),
    );

    renderWithQueryClient(<MarketPage />);

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveTextContent("DEGRADED");
    expect(banner).toHaveTextContent("88%");
    expect(banner).toHaveTextContent("vol");
  });

  it("renders gracefully when the engine has not published yet", async () => {
    vi.mocked(marketRiskApi.getLatest).mockResolvedValue(
      axiosResponse({
        status: "unavailable",
        checked_at: "2026-07-02T10:00:00+00:00",
        source: "market:risk:latest",
        risk: null,
        structure: {
          status: "unknown",
          snapshot: null,
          trade_date: null,
          asof: null,
          age_s: null,
          coverage_ratio: null,
          missing_components: [],
        },
        night_close: { available: false, status: "missing" },
      } satisfies MarketRiskLatest),
    );

    renderWithQueryClient(<MarketPage />);

    expect(
      await screen.findByText(/Market Risk 엔진이 아직 발행하지 않았습니다/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No component breakdown published yet"),
    ).toBeInTheDocument();
    expect(screen.getByText("밴드 미산출 — 매트릭스 대기 중")).toBeInTheDocument();
    // 이력이 비어 있으면 차트는 empty state로 렌더링된다.
    expect(
      screen.getAllByText("데이터 없음 — 수집/엔진 가동 후 표시됩니다").length,
    ).toBeGreaterThan(0);
    expect(screen.getByText("야간 종가 미수집")).toBeInTheDocument();
  });

  it("exposes accessible loading status while market risk is pending", async () => {
    vi.mocked(marketRiskApi.getLatest).mockReturnValue(
      new Promise(() => {}) as ReturnType<typeof marketRiskApi.getLatest>,
    );

    renderWithQueryClient(<MarketPage />);

    expect(
      await screen.findByRole("status", { name: "Loading market risk" }),
    ).toBeInTheDocument();
  });
});
