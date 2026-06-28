import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import type { AxiosResponse } from "axios";

import CoveragePage from "./coverage/page";
import EventContextPage from "./event-context/page";
import RiskPage from "./risk/page";
import SignalsPage from "./signals/page";
import TradesPage from "./trades/page";
import { StrategyPromotionBoard } from "@/components/builder/StrategyPromotionBoard";
import { INITIAL_STATE } from "@/hooks/useStrategyBuilder";
import type { StoredStrategy } from "@/types/builder";
import {
  coverageApi,
  decisionTraceApi,
  signalsApi,
  tradesApi,
  tradingApi,
} from "@/lib/dashboard/api";
import { eventContextApi } from "@/lib/dashboard/eventContext";
import { getStrategyPromotionSources } from "@/lib/dashboard/strategyBuilder";

vi.mock("@/components/dashboard/HeaderBar", () => ({
  default: () => <header aria-label="Cockpit header">KIS Cockpit</header>,
}));

vi.mock("@/hooks/dashboard/useStrategies", () => ({
  default: () => ({
    strategies: [],
    byAssetClass: () => [],
  }),
}));

vi.mock("@/contexts/dashboard/AssetClassContext", () => ({
  useAssetClass: () => ({
    selectedAsset: "stock",
    setSelectedAsset: vi.fn(),
  }),
}));

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => (
    <div data-testid="responsive-chart">{children}</div>
  ),
  LineChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  BarChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Bar: () => null,
}));

vi.mock("@/lib/dashboard/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/dashboard/api")>(
    "@/lib/dashboard/api",
  );
  return {
    ...actual,
    coverageApi: { getCoverage: vi.fn() },
    decisionTraceApi: { getDecisionTrace: vi.fn() },
    signalsApi: { getSignals: vi.fn(), getHistory: vi.fn() },
    tradesApi: {
      getTrades: vi.fn(),
      getByStrategy: vi.fn(),
      getClosedStatistics: vi.fn(),
      getClosedTrades: vi.fn(),
      getLifecycle: vi.fn(),
    },
    tradingApi: {
      getPositions: vi.fn(),
      getRiskExposure: vi.fn(),
    },
  };
});

vi.mock("@/lib/dashboard/eventContext", async () => {
  const actual = await vi.importActual<typeof import("@/lib/dashboard/eventContext")>(
    "@/lib/dashboard/eventContext",
  );
  return {
    ...actual,
    eventContextApi: { getDiagnostics: vi.fn() },
  };
});

vi.mock("@/lib/dashboard/strategyBuilder", async () => {
  const actual = await vi.importActual<typeof import("@/lib/dashboard/strategyBuilder")>(
    "@/lib/dashboard/strategyBuilder",
  );
  return {
    ...actual,
    getStrategyPromotionSources: vi.fn(),
  };
});

function renderWithQueryClient(ui: ReactNode) {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
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

describe("Quant Ops Workbench UI smoke coverage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders /risk empty exposure state with accessible refresh control", async () => {
    vi.mocked(tradingApi.getRiskExposure).mockResolvedValue(
      axiosResponse({
        asset_class: "stock",
        generated_at: "2026-06-22T09:10:00+09:00",
        portfolio: {
          equity_krw: 10_000_000,
          cash_krw: 9_500_000,
          gross_exposure_krw: 0,
          net_exposure_krw: 0,
          unrealized_pnl_krw: 0,
          realized_pnl_krw: 0,
          daily_pnl_krw: 0,
          daily_loss_krw: 0,
          open_positions: 0,
          exposure_to_equity_pct: 0,
          last_update: "2026-06-22T09:10:00+09:00",
        },
        by_strategy: [],
        by_symbol: [],
        notes: ["risk engine degraded but page should render"],
      }),
    );

    renderWithQueryClient(<RiskPage />);

    expect(await screen.findByRole("heading", { name: "Risk & Exposure" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh risk exposure" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Strategy Exposure" })).toBeInTheDocument();
    expect(await screen.findByText("No strategy exposure")).toBeInTheDocument();
    expect(screen.getByText("No symbol exposure")).toBeInTheDocument();
    expect(screen.getByText("risk engine degraded but page should render")).toBeInTheDocument();
  });

  it("exposes accessible loading status for /risk while exposure data is pending", async () => {
    const riskRequest = deferred<Awaited<ReturnType<typeof tradingApi.getRiskExposure>>>();
    vi.mocked(tradingApi.getRiskExposure).mockReturnValue(riskRequest.promise);

    renderWithQueryClient(<RiskPage />);

    expect(
      await screen.findByRole("status", { name: "Loading risk exposure" }),
    ).toBeInTheDocument();
  });

  it("renders negative daily loss with loss tone on /risk", async () => {
    vi.mocked(tradingApi.getRiskExposure).mockResolvedValue(
      axiosResponse({
        asset_class: "stock",
        generated_at: "2026-06-22T09:10:00+09:00",
        portfolio: {
          equity_krw: 10_000_000,
          cash_krw: 9_500_000,
          gross_exposure_krw: 0,
          net_exposure_krw: 0,
          unrealized_pnl_krw: 0,
          realized_pnl_krw: 0,
          daily_pnl_krw: 0,
          daily_loss_krw: -1000,
          open_positions: 0,
          exposure_to_equity_pct: 0,
          last_update: "2026-06-22T09:10:00+09:00",
        },
        by_strategy: [],
        by_symbol: [],
        notes: [],
      }),
    );

    renderWithQueryClient(<RiskPage />);

    expect(await screen.findByText("₩-1,000")).toHaveClass("text-loss");
  });

  it("renders /coverage missing-source evidence without live network", async () => {
    vi.mocked(coverageApi.getCoverage).mockResolvedValue(
      axiosResponse({
        asset_class: "stock",
        generated_at: "2026-06-22T09:11:00+09:00",
        sources: [
          {
            name: "daily_indicators",
            key: "daily:stock",
            available: false,
            count: null,
            updated_at: null,
            symbols: [],
            missing_symbols: ["005930", "000660"],
            metadata: {},
          },
        ],
        experiment_coverage: [],
        missing_evidence: ["daily_indicators"],
        notes: ["coverage snapshot is partial"],
      }),
    );

    renderWithQueryClient(<CoveragePage />);

    expect(await screen.findByRole("heading", { name: "Coverage Explorer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Refresh coverage" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Runtime Sources" })).toBeInTheDocument();
    expect(await screen.findByText("Missing evidence: daily_indicators")).toBeInTheDocument();
    expect(screen.getByText("missing")).toBeInTheDocument();
    expect(screen.getByText("No latest experiment coverage")).toBeInTheDocument();
  });

  it("exposes accessible loading status for /coverage while source data is pending", async () => {
    const coverageRequest = deferred<Awaited<ReturnType<typeof coverageApi.getCoverage>>>();
    vi.mocked(coverageApi.getCoverage).mockReturnValue(coverageRequest.promise);

    renderWithQueryClient(<CoveragePage />);

    expect(
      await screen.findByRole("status", { name: "Loading coverage sources" }),
    ).toBeInTheDocument();
  });

  it("renders /signals decision trace after selecting a signal", async () => {
    vi.mocked(signalsApi.getSignals).mockResolvedValue(
      axiosResponse({
        total: 1,
        page: 1,
        limit: 50,
        signals: [
          {
            id: "sig-1",
            asset_class: "stock",
            strategy: "setup_a_gap_reversion",
            symbol: "101S6000",
            side: "BUY",
            signal_type: "entry",
            confidence: 0.72,
            strength: 0.72,
            price: 390.25,
            timestamp: "2026-06-27T00:20:00+00:00",
            executed: false,
          },
        ],
      }),
    );
    vi.mocked(decisionTraceApi.getDecisionTrace).mockResolvedValue(
      axiosResponse({
        signal: {
          id: "sig-1",
          asset_class: "stock",
          symbol: "101S6000",
          strategy: "setup_a_gap_reversion",
          side: "BUY",
          signal_type: "entry",
          status: "generated",
          reason: "gap_reversion_candidate",
          confidence: 0.72,
          strength: 0.72,
          price: 390.25,
          timestamp: "2026-06-27T00:20:00+00:00",
        },
        summary: {
          state: "orderable",
          text: "setup_a_gap_reversion generated BUY 101S6000.",
          warnings: [],
        },
        llm_context: {
          status: "ok",
          overall_signal: "BULLISH",
          confidence: 0.71,
          risk_mode: "risk_on",
          regime: "trend",
          risk_score: 0.22,
          captured_at: "2026-06-27T00:10:00+00:00",
          source: "llm_premarket_briefing",
        },
        strategy_inputs: {
          setup_type: "setup_a",
          indicators: { gap_pct: -0.42 },
          thresholds: { min_gap_pct: 0.3 },
          event_evidence: {},
          raw_reason: "gap_reversion_candidate",
        },
        risk_orderability: {
          reject_stage: null,
          reject_reason: null,
          orderability_state: "paper_orderable",
          orderability_details: {},
          risk_state: null,
          risk_details: {},
        },
        lineage: {
          signal_id: "sig-1",
          order_id: null,
          fill_id: null,
          position_id: null,
          trade_id: null,
        },
        lifecycle: {
          status: "missing",
          steps: [],
          warnings: ["no_lifecycle_evidence"],
        },
        scorecard: {
          status: "missing",
          facet: null,
          date_kst: null,
          captured_at: null,
          confidence: null,
          correct: null,
          value: null,
          economic_proxy: null,
          baseline_value: null,
          edge: null,
          scored_at: null,
          detail: {},
        },
        evidence_gaps: [],
      }),
    );

    renderWithQueryClient(<SignalsPage />);

    expect(await screen.findByRole("heading", { name: "Trading Signals" })).toBeInTheDocument();
    const traceButtons = await screen.findAllByRole("button", {
      name: "View trace for 101S6000",
    });
    await userEvent.click(traceButtons[0]);

    expect(await screen.findByRole("region", { name: "Decision Trace" })).toBeInTheDocument();
    expect(screen.getByText("BULLISH")).toBeInTheDocument();
    expect(decisionTraceApi.getDecisionTrace).toHaveBeenCalledWith("sig-1", {
      asset_class: "stock",
    });
  });

  it("renders /trades live lifecycle drill-in from mocked responses", async () => {
    vi.mocked(tradesApi.getTrades).mockResolvedValue(
      axiosResponse({
        total: 1,
        trades: [
          {
            id: "trade-1",
            strategy: "opening_volume_surge",
            symbol: "005930",
            side: "BUY",
            quantity: 10,
            entry_price: 70000,
            exit_price: 71000,
            pnl: 10000,
            pnl_pct: 1.4,
            entry_time: "2026-06-22T09:01:00+09:00",
            exit_time: "2026-06-22T09:20:00+09:00",
          },
        ],
      }),
    );
    vi.mocked(tradesApi.getByStrategy).mockResolvedValue(axiosResponse([]));
    vi.mocked(tradesApi.getLifecycle).mockResolvedValue(
      axiosResponse({
        asset_class: "stock",
        as_of: "2026-06-22T09:21:00+09:00",
        filters: { trade_id: "trade-1" },
        lineage: {
          signal_id: "sig-1",
          order_id: "ord-1",
          fill_id: "fill-1",
          trade_id: "trade-1",
          position_id: "pos-1",
        },
        steps: [
          {
            stage: "signal",
            label: "Signal",
            status: "ok",
            id: "sig-1",
            timestamp: "2026-06-22T09:00:00+09:00",
            source: "runtime_ledger",
            summary: "entry signal accepted",
            details: { strategy: "opening_volume_surge" },
          },
        ],
        warnings: [],
      }),
    );

    renderWithQueryClient(<TradesPage />);

    expect(await screen.findByRole("heading", { name: "Trade History" })).toBeInTheDocument();
    expect(await screen.findAllByText("005930")).not.toHaveLength(0);
    await userEvent.click(screen.getAllByRole("button", { name: "View lifecycle for 005930" })[0]);

    expect(await screen.findByRole("heading", { name: "Lifecycle 005930" })).toBeInTheDocument();
    expect(screen.getByText("entry signal accepted")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close lifecycle panel" })).toBeInTheDocument();
  });

  it("exposes /trades source tabs with accessible roles and switches to DB history", async () => {
    vi.mocked(tradesApi.getTrades).mockResolvedValue(
      axiosResponse({ total: 0, trades: [] }),
    );
    vi.mocked(tradesApi.getByStrategy).mockResolvedValue(axiosResponse([]));
    vi.mocked(tradesApi.getClosedStatistics).mockResolvedValue(
      axiosResponse({
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
        win_rate: 0,
        total_pnl: 0,
        avg_pnl: 0,
        max_win: 0,
        max_loss: 0,
        profit_factor: 0,
      }),
    );
    vi.mocked(tradesApi.getClosedTrades).mockResolvedValue(axiosResponse([]));
    vi.mocked(tradingApi.getPositions).mockResolvedValue(axiosResponse([]));

    renderWithQueryClient(<TradesPage />);

    expect(screen.getByRole("tablist", { name: "Trade history data source" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Strategy filter" })).toBeInTheDocument();
    const liveTab = screen.getByRole("tab", { name: "Live (Redis)" });
    const historyTab = screen.getByRole("tab", { name: "History (DB)" });
    expect(liveTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: "Refresh live trades" })).toBeInTheDocument();
    await waitFor(() =>
      expect(tradesApi.getByStrategy).toHaveBeenCalledWith({ asset_class: "stock" }),
    );

    await userEvent.click(historyTab);

    expect(historyTab).toHaveAttribute("aria-selected", "true");
    expect(liveTab).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("button", { name: "Refresh trade history" })).toBeInTheDocument();
    expect(await screen.findByText("Closed Trades")).toBeInTheDocument();
  });

  it("exposes accessible loading status while /trades live data is pending", async () => {
    const tradesRequest = deferred<Awaited<ReturnType<typeof tradesApi.getTrades>>>();
    vi.mocked(tradesApi.getTrades).mockReturnValue(tradesRequest.promise);
    vi.mocked(tradesApi.getByStrategy).mockResolvedValue(axiosResponse([]));

    renderWithQueryClient(<TradesPage />);

    expect(
      await screen.findByRole("status", { name: "Loading live trades" }),
    ).toBeInTheDocument();
  });

  it("supports keyboard navigation between /trades source tabs", async () => {
    vi.mocked(tradesApi.getTrades).mockResolvedValue(
      axiosResponse({ total: 0, trades: [] }),
    );
    vi.mocked(tradesApi.getByStrategy).mockResolvedValue(axiosResponse([]));
    vi.mocked(tradesApi.getClosedStatistics).mockResolvedValue(
      axiosResponse({
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
        win_rate: 0,
        total_pnl: 0,
        avg_pnl: 0,
        max_win: 0,
        max_loss: 0,
        profit_factor: 0,
      }),
    );
    vi.mocked(tradesApi.getClosedTrades).mockResolvedValue(axiosResponse([]));
    vi.mocked(tradingApi.getPositions).mockResolvedValue(axiosResponse([]));

    renderWithQueryClient(<TradesPage />);

    const liveTab = screen.getByRole("tab", { name: "Live (Redis)" });
    const historyTab = screen.getByRole("tab", { name: "History (DB)" });
    liveTab.focus();

    await userEvent.keyboard("{ArrowRight}");

    expect(historyTab).toHaveAttribute("aria-selected", "true");
    expect(historyTab).toHaveFocus();
  });

  it("renders /event-context sparse diagnostics and empty operator state", async () => {
    vi.mocked(eventContextApi.getDiagnostics).mockResolvedValue(
      axiosResponse({
        asset_class: "futures",
        generated_at: "2026-06-22T09:12:00+09:00",
        event_scores: {
          latest_score_at: null,
          age_seconds: null,
          total_count: 0,
          recent_count: 0,
          sparsity_ratio: 0,
          sparse: true,
          status: "sparse",
          by_source: [],
          by_impact_tier: {},
          warnings: ["event scores sparse"],
        },
        source_timeline: [],
        setup_c: {
          strategy: "setup_c_event_reaction",
          enabled: true,
          window_minutes: 90,
          min_impact_tier: 2,
          last_eval_at: null,
          last_reject_reason: null,
          candidate_count: 0,
          blocked_count: 0,
          missing_count: 0,
          candidates: [],
          blocked: [],
          missing_evidence: [],
          blocked_reason_distribution: [],
          notes: [],
        },
        missing_evidence: ["macro_calendar"],
        notes: [],
      }),
    );

    renderWithQueryClient(<EventContextPage />);

    expect(
      await screen.findByRole("heading", { name: "Event Context Diagnostics" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Refresh event context diagnostics" }),
    ).toBeInTheDocument();
    expect(await screen.findByText(/Missing event context evidence:/)).toBeInTheDocument();
    expect(screen.getByText("No event-score source breakdown")).toBeInTheDocument();
    expect(screen.getByText("No additional notes from diagnostics.")).toBeInTheDocument();
  });

  it("exposes accessible loading status for /event-context while diagnostics are pending", async () => {
    const diagnosticsRequest = deferred<Awaited<ReturnType<typeof eventContextApi.getDiagnostics>>>();
    vi.mocked(eventContextApi.getDiagnostics).mockReturnValue(diagnosticsRequest.promise);

    renderWithQueryClient(<EventContextPage />);

    expect(
      await screen.findByRole("status", { name: "Loading event context diagnostics" }),
    ).toBeInTheDocument();
  });

  it("renders builder promotion board with degraded evidence source messaging", async () => {
    vi.mocked(getStrategyPromotionSources).mockResolvedValueOnce({
      registered: [],
      activity: [],
      latestReport: null,
      paperComparison: null,
      sourceErrors: ["registered: unavailable"],
    });
    const localStrategies: StoredStrategy[] = [
      {
        id: "draft-1",
        name: "Draft Smoke Strategy",
        createdAt: "2026-06-22T09:00:00+09:00",
        updatedAt: "2026-06-22T09:00:00+09:00",
        state: {
          ...INITIAL_STATE,
          metadata: {
            ...INITIAL_STATE.metadata,
            id: "draft-1",
            name: "Draft Smoke Strategy",
            description: "local draft should still appear",
          },
        },
      },
    ];

    render(<StrategyPromotionBoard localStrategies={localStrategies} presetStrategies={[]} />);

    expect(await screen.findByRole("heading", { name: "Strategy Promotion Kanban" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("1 strategies")).toBeInTheDocument());
    expect(screen.getByText("Evidence source unavailable: registered: unavailable")).toBeInTheDocument();
    expect(screen.getByText("Draft Smoke Strategy")).toBeInTheDocument();
    expect(screen.getByText("Live Gated")).toBeInTheDocument();
  });

  it("keeps the builder promotion board read-only while evidence is loading", async () => {
    const promotionRequest = deferred<Awaited<ReturnType<typeof getStrategyPromotionSources>>>();
    vi.mocked(getStrategyPromotionSources).mockReturnValue(promotionRequest.promise);

    render(<StrategyPromotionBoard localStrategies={[]} presetStrategies={[]} />);

    expect(
      await screen.findByRole("status", { name: "Loading promotion evidence" }),
    ).toBeInTheDocument();
    expect(screen.getByText("read-only")).toBeInTheDocument();
    expect(screen.getByText("paper-safe")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /live|enable|submit|order/i })).not.toBeInTheDocument();
  });
});
