import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DecisionTraceResponse } from "@/lib/dashboard/decisionTrace";
import DecisionTracePanel from "./DecisionTracePanel";

const baseTrace: DecisionTraceResponse = {
  signal: {
    id: "sig-1",
    asset_class: "futures",
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
    indicators: { gap_pct: -0.42, atr: 1.8 },
    thresholds: { min_gap_pct: 0.3 },
    event_evidence: {},
    raw_reason: "gap_reversion_candidate",
  },
  risk_orderability: {
    reject_stage: null,
    reject_reason: null,
    orderability_state: "paper_orderable",
    orderability_details: { state: "paper_orderable" },
    risk_state: null,
    risk_details: {},
  },
  lineage: {
    signal_id: "sig-1",
    order_id: "ord-1",
    fill_id: "fill-1",
    position_id: null,
    trade_id: null,
  },
  lifecycle: {
    status: "partial",
    steps: [
      {
        stage: "signal",
        label: "Signal",
        status: "generated",
        id: "sig-1",
        timestamp: "2026-06-27T00:20:00+00:00",
        source: "runtime_ledger",
        summary: "BUY 101S6000",
        details: { strategy: "setup_a_gap_reversion" },
      },
    ],
    warnings: ["partial_legacy_lineage"],
  },
  scorecard: {
    status: "ok",
    facet: "direction",
    date_kst: "2026-06-27",
    captured_at: "2026-06-27T00:05:00+00:00",
    confidence: 0.71,
    correct: true,
    value: 0.28,
    economic_proxy: 0.18,
    baseline_value: 0.1,
    edge: 0.18,
    scored_at: "2026-06-27T07:00:00+00:00",
    detail: { outcome: "up" },
  },
  evidence_gaps: [],
};

const gateShadowBlock = {
  mode: "shadow",
  band: "HIGH",
  score: 74.2,
  regime: "RISK_OFF",
  would_block: true,
  allow: true,
  size_factor: 0.5,
  min_confidence: null,
  reason: "market_risk band=HIGH score=74.2 rule=block_new_long",
  degraded: false,
  stale: false,
};

describe("DecisionTracePanel", () => {
  it("renders full decision trace evidence in a named region", () => {
    render(
      <DecisionTracePanel
        trace={baseTrace}
        onClose={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByRole("region", { name: "Decision Trace" })).toBeInTheDocument();
    expect(screen.getByText("101S6000")).toBeInTheDocument();
    expect(screen.getByText("BULLISH")).toBeInTheDocument();
    expect(screen.getByText("paper_orderable")).toBeInTheDocument();
    expect(screen.getByText("direction")).toBeInTheDocument();
    expect(screen.getByText("+0.18")).toBeInTheDocument();
    expect(screen.getByText("BUY 101S6000")).toBeInTheDocument();
    // 게이트 배선 전 신호(market_risk_gate 부재)는 섹션을 렌더하지 않는다.
    expect(screen.queryByText("Market Risk Gate")).not.toBeInTheDocument();
  });

  it("renders the market risk gate section with shadow would-block wording", () => {
    render(
      <DecisionTracePanel
        trace={{ ...baseTrace, market_risk_gate: gateShadowBlock }}
        onClose={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("Market Risk Gate")).toBeInTheDocument();
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    expect(screen.getByText("score 74.2")).toBeInTheDocument();
    expect(screen.getByText("shadow — 미집행")).toBeInTheDocument();
    expect(screen.getByText("shadow — 차단됐을 것")).toBeInTheDocument();
    expect(
      screen.getByText("market_risk band=HIGH score=74.2 rule=block_new_long"),
    ).toBeInTheDocument();
    expect(screen.getByText("0.5 (50%)")).toBeInTheDocument();
    expect(screen.getByText("RISK_OFF")).toBeInTheDocument();
  });

  it("marks an enforce-mode block as actually blocked", () => {
    render(
      <DecisionTracePanel
        trace={{
          ...baseTrace,
          market_risk_gate: {
            ...gateShadowBlock,
            mode: "enforce",
            allow: false,
            band: "CRITICAL",
            score: 91.3,
            reason: "market_risk band=CRITICAL score=91.3 rule=block_all_entries",
          },
        }}
        onClose={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("enforce — 집행 중")).toBeInTheDocument();
    expect(screen.getByText("차단됨")).toBeInTheDocument();
    expect(screen.queryByText("shadow — 차단됐을 것")).not.toBeInTheDocument();
  });

  it("shows a pass verdict and fail-open flags when the gate degrades", () => {
    render(
      <DecisionTracePanel
        trace={{
          ...baseTrace,
          market_risk_gate: {
            ...gateShadowBlock,
            would_block: false,
            size_factor: 1.0,
            reason: "fail_open:degraded",
            degraded: true,
          },
        }}
        onClose={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("통과")).toBeInTheDocument();
    expect(screen.getByText("fail_open:degraded")).toBeInTheDocument();
    expect(
      screen.getByText(/degraded — fail-open 통과/),
    ).toBeInTheDocument();
  });

  it("renders missing LLM context and unscorable score without implying failure", () => {
    render(
      <DecisionTracePanel
        trace={{
          ...baseTrace,
          llm_context: { status: "not_available" },
          scorecard: {
            ...baseTrace.scorecard,
            status: "ok",
            correct: null,
            detail: { reason: "market_data_gap" },
          },
          evidence_gaps: [
            {
              code: "llm_context_not_available",
              severity: "warning",
              message: "No LLM market context is linked to this signal.",
            },
          ],
        }}
        onClose={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("not_available")).toBeInTheDocument();
    expect(screen.getByText("unscorable")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("No LLM market context");
  });

  it("does not render a Trade ID link when trade_id is null", () => {
    render(
      <DecisionTracePanel
        trace={baseTrace}
        onClose={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    // trade_id is null in baseTrace → plain "not available", no link.
    expect(
      screen.queryByRole("link", { name: /trd-/ }),
    ).not.toBeInTheDocument();
  });

  it("deep-links Trade ID to /trades?highlight=<id> when present", () => {
    render(
      <DecisionTracePanel
        trace={{
          ...baseTrace,
          lineage: { ...baseTrace.lineage, trade_id: "trd-42" },
        }}
        onClose={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    const link = screen.getByRole("link", { name: "trd-42" });
    expect(link).toHaveAttribute("href", "/trades?highlight=trd-42");
  });

  it("exposes close and refresh controls", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onRefresh = vi.fn();

    render(
      <DecisionTracePanel
        trace={baseTrace}
        onClose={onClose}
        onRefresh={onRefresh}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Close decision trace" }));
    await user.click(screen.getByRole("button", { name: "Refresh decision trace" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
