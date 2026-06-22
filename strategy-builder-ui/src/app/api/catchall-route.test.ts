import { describe, expect, it, vi, afterEach } from "vitest";
import { DELETE, GET, POST, PUT } from "./[...path]/route";
import type { NextRequest } from "next/server";

function requestFor(path: string): NextRequest {
  const url = `http://localhost:3100${path}`;
  return {
    method: "GET",
    headers: new Headers(),
    nextUrl: new URL(url),
  } as NextRequest;
}

function requestWithMethod(path: string, method: string): NextRequest {
  const request = requestFor(path) as NextRequest & {
    method: string;
    arrayBuffer: () => Promise<ArrayBuffer>;
  };
  request.method = method;
  request.arrayBuffer = async () => new ArrayBuffer(0);
  return request;
}

function contextFor(path: string[]) {
  return { params: { path } };
}

describe("strategy-builder-ui API catch-all proxy", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("proxies Quant Ops Workbench dashboard routes as same-origin /api roots", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" })));

    const response = await GET(
      requestFor("/api/health/summary?asset_class=futures"),
      contextFor(["health", "summary"]),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://localhost:5080/api/health/summary?asset_class=futures",
    );
  });

  it("keeps bare /api/strategies on the STS registry route", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ strategies: [] })));

    const response = await GET(
      requestFor("/api/strategies"),
      contextFor(["strategies"]),
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://localhost:5080/api/strategies",
    );
  });

  it("keeps Strategy Builder /api/strategies/* compatibility routes on kis-builder", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ strategies: [] })));

    const response = await GET(
      requestFor("/api/strategies/custom"),
      contextFor(["strategies", "custom"]),
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://localhost:5080/api/kis-builder/strategies/custom",
    );
  });

  it("does not fake success for mutating Strategy Builder compatibility routes when upstream is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await POST(
      requestWithMethod("/api/strategies/preview-code", "POST"),
      contextFor(["strategies", "preview-code"]),
    );
    const body = await response.json();

    expect(response.status).toBe(503);
    expect(body.upstream_path).toBe("/api/kis-builder/strategies/preview-code");
  });

  it("does not fake success for PUT and DELETE routes when upstream is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const putResponse = await PUT(
      requestWithMethod("/api/kis-builder/registered/example", "PUT"),
      contextFor(["kis-builder", "registered", "example"]),
    );
    const deleteResponse = await DELETE(
      requestWithMethod("/api/kis-builder/registered/example", "DELETE"),
      contextFor(["kis-builder", "registered", "example"]),
    );

    expect(putResponse.status).toBe(503);
    expect((await putResponse.json()).upstream_path).toBe("/api/kis-builder/registered/example");
    expect(deleteResponse.status).toBe(503);
    expect((await deleteResponse.json()).upstream_path).toBe("/api/kis-builder/registered/example");
  });

  it("returns degraded Strategy Builder GET fallback for /api/strategies/* compatibility routes", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/strategies/custom"),
      contextFor(["strategies", "custom"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(response.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(body.strategies).toEqual([]);
    expect(body.notes[0]).toContain("/api/kis-builder/strategies/custom");
  });

  it("marks direct strategies registry fallback as unavailable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/strategies?asset_class=stock"),
      contextFor(["strategies"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(response.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(body.strategies).toEqual([]);
    expect(body.notes[0]).toContain("Dashboard API unavailable");
  });

  it("returns a local degraded risk payload when the upstream dashboard is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/trading/risk-exposure?asset_class=futures"),
      contextFor(["trading", "risk-exposure"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.asset_class).toBe("futures");
    expect(body.portfolio.open_positions).toBe(0);
    expect(body.notes[0]).toContain("Dashboard API unavailable");
  });

  it("returns degraded risk payload when the upstream dashboard returns 500", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "boom" }), { status: 500 }),
    );

    const response = await GET(
      requestFor("/api/trading/risk-exposure?asset_class=futures"),
      contextFor(["trading", "risk-exposure"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(response.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(body.asset_class).toBe("futures");
    expect(body.notes[0]).toContain("Dashboard API unavailable");
  });

  it("returns degraded coverage payload when the upstream dashboard returns 404", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "missing" }), { status: 404 }),
    );

    const response = await GET(
      requestFor("/api/coverage?asset_class=futures"),
      contextFor(["coverage"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(response.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(body.asset_class).toBe("futures");
    expect(body.missing_evidence).toContain("dashboard_api");
  });

  it("marks health fallback as degraded instead of healthy when the upstream dashboard is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/health/summary?asset_class=futures"),
      contextFor(["health", "summary"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.processes[0].alive).toBe(false);
    expect(body.data_sources[0].fresh_ratio).toBe(0);
    expect(body.ops_summary.health.dashboard).toBe("degraded");
  });

  it("returns a contract-compatible signal history fallback", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/signals/history?days=14&asset_class=futures"),
      contextFor(["signals", "history"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.history).toEqual([]);
    expect(body.total_signals).toBe(0);
    expect(body.days).toBe(14);
    expect(body.notes[0]).toContain("Dashboard API unavailable");
  });

  it("returns explicit degraded lifecycle payload when the dashboard is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/trades/lifecycle?trade_id=trade-1&symbol=005930&asset_class=futures"),
      contextFor(["trades", "lifecycle"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.asset_class).toBe("futures");
    expect(body.steps[0].source).toBe("not_available");
    expect(body.warnings).toContain("dashboard_api_unavailable");
  });

  it("returns explicit degraded event context payload when the dashboard is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/event-context/diagnostics?asset_class=futures"),
      contextFor(["event-context", "diagnostics"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.event_scores.status).toBe("unknown");
    expect(body.missing_evidence).toContain("dashboard_api");
  });

  it("returns explicit degraded coverage payload when the dashboard is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/coverage?asset_class=futures"),
      contextFor(["coverage"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(response.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(body.asset_class).toBe("futures");
    expect(body.missing_evidence).toContain("dashboard_api");
    expect(body.notes[0]).toContain("Dashboard API unavailable");
  });

  it("returns explicit degraded experiment comparison payload when the dashboard is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/experiments/latest/compare-paper"),
      contextFor(["experiments", "latest", "compare-paper"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.source.ledger_available).toBe(false);
    expect(body.missing_evidence).toContain("dashboard_api");
  });

  it("returns explicit degraded Strategy Builder promotion sources when the dashboard is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const registered = await GET(
      requestFor("/api/kis-builder/registered"),
      contextFor(["kis-builder", "registered"]),
    );
    const activity = await GET(
      requestFor("/api/kis-builder/registered/activity"),
      contextFor(["kis-builder", "registered", "activity"]),
    );
    const strategies = await GET(
      requestFor("/api/kis-builder/strategies"),
      contextFor(["kis-builder", "strategies"]),
    );

    expect(registered.status).toBe(200);
    expect(await registered.json()).toMatchObject({ strategies: [], total: 0 });
    expect(activity.status).toBe(200);
    expect(await activity.json()).toMatchObject({ activity: [] });
    expect(strategies.status).toBe(200);
    expect(await strategies.json()).toMatchObject({ strategies: [] });
  });

  it("marks array-contract trade fallbacks with a degraded response header", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const byStrategy = await GET(
      requestFor("/api/trades/by-strategy"),
      contextFor(["trades", "by-strategy"]),
    );
    const closed = await GET(
      requestFor("/api/trades/closed?asset_class=futures"),
      contextFor(["trades", "closed"]),
    );
    const fills = await GET(
      requestFor("/api/trades/fills?asset_class=futures"),
      contextFor(["trades", "fills"]),
    );

    expect(byStrategy.status).toBe(200);
    expect(byStrategy.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(await byStrategy.json()).toEqual([]);
    expect(closed.status).toBe(200);
    expect(closed.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(await closed.json()).toEqual([]);
    expect(fills.status).toBe(200);
    expect(fills.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(await fills.json()).toMatchObject({ fills: [] });
  });

  it("returns a local unauthenticated status when the builder auth upstream is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/auth/status"),
      contextFor(["auth", "status"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.authenticated).toBe(false);
    expect(body.mode).toBe("vps");
  });
});
