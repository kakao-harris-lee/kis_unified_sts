import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
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

// The proxy reads KIS_BUILDER_API_KEY / DASHBOARD_API_KEY per request, so a key
// in the developer's or CI runner's shell would make the unauthenticated cases
// below 401 and read as a regression. Clear both for every test in this file and
// put the ambient values back afterwards; the describes that need a key set one
// explicitly on top of this clean slate.
const AUTH_ENV_VARS = ["KIS_BUILDER_API_KEY", "DASHBOARD_API_KEY"] as const;
const ambientAuthEnv = new Map<string, string | undefined>();

beforeEach(() => {
  for (const name of AUTH_ENV_VARS) {
    ambientAuthEnv.set(name, process.env[name]);
    delete process.env[name];
  }
});

afterEach(() => {
  for (const name of AUTH_ENV_VARS) {
    const saved = ambientAuthEnv.get(name);
    if (saved === undefined) delete process.env[name];
    else process.env[name] = saved;
  }
  ambientAuthEnv.clear();
});

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
      "http://localhost:5081/api/health/summary?asset_class=futures",
    );
  });

  it("proxies feedback report routes to the STS dashboard (Phase 6B)", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(JSON.stringify({ kind: "weekly", reports: [] })));

    const response = await GET(
      requestFor("/api/reports/feedback?kind=weekly&limit=8"),
      contextFor(["reports", "feedback"]),
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://localhost:5081/api/reports/feedback?kind=weekly&limit=8",
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
      "http://localhost:5081/api/strategies",
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
      "http://localhost:5081/api/kis-builder/strategies/custom",
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

  it("returns explicit degraded signal trace payload when the dashboard is offline", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestFor("/api/signals/sig-1/trace?asset_class=futures"),
      contextFor(["signals", "sig-1", "trace"]),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(response.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
    expect(body.signal.id).toBe("sig-1");
    expect(body.summary.state).toBe("unknown");
    expect(body.llm_context.status).toBe("unknown");
    expect(body.lifecycle.status).toBe("not_available");
    expect(body.evidence_gaps[0].code).toBe("dashboard_api_unavailable");
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


describe("TOS projection proxy boundary", () => {
  afterEach(() => vi.restoreAllMocks());
  it("forwards only the projection GET without a cached or fabricated response", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ available: false }));
    const response = await GET(requestFor("/api/tos/projection"), contextFor(["tos", "projection"]));
    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe("http://localhost:5081/api/tos/projection");
    expect(fetchMock.mock.calls[0][1]?.cache).toBe("no-store");
    expect(await response.json()).toEqual({ available: false });
  });
  it("refuses mutation and unknown TOS paths without reaching upstream", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    for (const [method, handler] of [["POST", POST], ["PUT", PUT], ["DELETE", DELETE]] as const) {
      const response = await handler(requestWithMethod("/api/tos/projection", method), contextFor(["tos", "projection"]));
      expect(response.status).toBe(405);
    }
    const response = await GET(requestFor("/api/tos/rearm"), contextFor(["tos", "rearm"]));
    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it.each([
    [["tos", "projection", "extra"], "/api/tos/projection/extra"],
    [["tos"], "/api/tos"],
    [["tos", "projection", ""], "/api/tos/projection/"],
  ])("refuses %s instead of treating it as the projection", async (path, url) => {
    // Exercises the `path.length === 2 && path[1] === "projection"` arm: with the
    // length check removed, the first case proxies as the projection.
    const fetchMock = vi.spyOn(globalThis, "fetch");
    const response = await GET(requestFor(url), contextFor(path));
    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it.each([401, 403, 503])("preserves upstream status %s instead of inventing an empty healthy snapshot", async (status) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ detail: "unavailable" }, { status }));
    const response = await GET(requestFor("/api/tos/projection"), contextFor(["tos", "projection"]));
    expect(response.status).toBe(status);
  });
  it("reports network failure as 503", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    const response = await GET(requestFor("/api/tos/projection"), contextFor(["tos", "projection"]));
    expect(response.status).toBe(503);
  });
});


// ---------------------------------------------------------------------------
// #861 review note f — the proxy attaches the server-side dashboard key to
// every upstream call, so it must authenticate the caller first. Caddy routes
// most /api roots straight to dashboard:8001, but coverage, event-context,
// market-risk, portfolio and reports reach the dashboard ONLY through here, so
// before this guard those five answered 200 with no key while the identical
// paths 401'd on the dashboard directly.
//
// Design decision recorded by these tests: there is NO public exception. The
// compat roots (auth/account/orders/market/files/symbols/experiments) are
// authenticated too — every browser caller already attaches X-API-Key from
// NEXT_PUBLIC_API_KEY (src/lib/api/client.ts since #469,
// src/lib/dashboard/client.ts), and the one header-less consumer (the weekly
// report <a href> in app/risk/components/FeedbackSummaryCard.tsx) now
// downloads through that authenticated client instead.
// ---------------------------------------------------------------------------

const PROXY_ONLY_ROOTS: ReadonlyArray<readonly [string, string[]]> = [
  ["/api/coverage?asset_class=futures", ["coverage"]],
  ["/api/event-context/diagnostics", ["event-context", "diagnostics"]],
  ["/api/market-risk", ["market-risk"]],
  ["/api/portfolio/equity", ["portfolio", "equity"]],
  ["/api/reports/feedback?kind=weekly", ["reports", "feedback"]],
];

const COMPAT_ROOTS: ReadonlyArray<readonly [string, string[]]> = [
  ["/api/auth/status", ["auth", "status"]],
  ["/api/account/info", ["account", "info"]],
  ["/api/orders/pending", ["orders", "pending"]],
  ["/api/market/price/005930", ["market", "price", "005930"]],
  ["/api/files/export", ["files", "export"]],
  ["/api/symbols/status", ["symbols", "status"]],
  ["/api/experiments/latest", ["experiments", "latest"]],
];

describe("proxy authenticates callers before lending the dashboard key", () => {
  const SERVER_KEY = "proxy-server-key";

  // The file-level hook already cleared both vars; this only adds the one key
  // these tests authenticate against.
  beforeEach(() => {
    process.env.KIS_BUILDER_API_KEY = SERVER_KEY;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  function requestWithKey(path: string, key: string | null): NextRequest {
    const headers = new Headers();
    if (key !== null) headers.set("X-API-Key", key);
    return {
      method: "GET",
      headers,
      nextUrl: new URL(`http://localhost:3100${path}`),
    } as NextRequest;
  }

  it.each(PROXY_ONLY_ROOTS)(
    "rejects %s with 401 when the caller presents no key",
    async (url, path) => {
      const fetchMock = vi.spyOn(globalThis, "fetch");

      const response = await GET(requestFor(url), contextFor(path));

      expect(response.status).toBe(401);
      expect(await response.json()).toEqual({ detail: "Invalid or missing API key" });
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it.each(PROXY_ONLY_ROOTS)(
    "forwards %s upstream with the server key once the caller authenticates",
    async (url, path) => {
      const fetchMock = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValue(Response.json({ ok: true }));

      const response = await GET(
        requestWithKey(url, SERVER_KEY),
        contextFor(path),
      );

      expect(response.status).toBe(200);
      expect(fetchMock).toHaveBeenCalledTimes(1);
      const forwarded = new Headers(fetchMock.mock.calls[0][1]?.headers as HeadersInit);
      expect(forwarded.get("X-API-Key")).toBe(SERVER_KEY);
    },
  );

  it.each(COMPAT_ROOTS)(
    "rejects compat root %s with 401 too — no public exception",
    async (url, path) => {
      const fetchMock = vi.spyOn(globalThis, "fetch");

      const response = await GET(requestFor(url), contextFor(path));

      expect(response.status).toBe(401);
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it.each(COMPAT_ROOTS)(
    "forwards compat root %s to kis-builder with the server key when authenticated",
    async (url, path) => {
      const fetchMock = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValue(Response.json({ ok: true }));

      const response = await GET(
        requestWithKey(url, SERVER_KEY),
        contextFor(path),
      );

      expect(response.status).toBe(200);
      expect(String(fetchMock.mock.calls[0][0])).toContain("/api/kis-builder/");
      const forwarded = new Headers(fetchMock.mock.calls[0][1]?.headers as HeadersInit);
      expect(forwarded.get("X-API-Key")).toBe(SERVER_KEY);
    },
  );

  it("rejects the Caddy-direct roots through the dev-server proxy as well", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const caddyDirect: ReadonlyArray<readonly [string, string[]]> = [
      ["/api/trades?page=1", ["trades"]],
      ["/api/signals", ["signals"]],
      ["/api/trading/status", ["trading", "status"]],
      ["/api/strategies", ["strategies"]],
      ["/api/kis-builder/registered", ["kis-builder", "registered"]],
      ["/api/tos/projection", ["tos", "projection"]],
    ];
    for (const [url, path] of caddyDirect) {
      const response = await GET(requestFor(url), contextFor(path));
      expect(response.status).toBe(401);
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each(["POST", "PUT", "DELETE"] as const)(
    "rejects unauthenticated %s before reading the body",
    async (method) => {
      const fetchMock = vi.spyOn(globalThis, "fetch");
      const handler = { POST, PUT, DELETE }[method];
      const request = requestWithMethod("/api/kis-builder/register-paper", method);
      const arrayBuffer = vi.fn(async () => new ArrayBuffer(0));
      (request as unknown as { arrayBuffer: () => Promise<ArrayBuffer> }).arrayBuffer =
        arrayBuffer;

      const response = await handler(request, contextFor(["kis-builder", "register-paper"]));

      expect(response.status).toBe(401);
      expect(arrayBuffer).not.toHaveBeenCalled();
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("answers 401 rather than 404 for an unsupported path, so roots stay unenumerable", async () => {
    const response = await GET(
      requestFor("/api/definitely-not-a-root"),
      contextFor(["definitely-not-a-root"]),
    );

    expect(response.status).toBe(401);
  });

  it("does not serve the degraded empty state to an unauthenticated caller", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(requestFor("/api/coverage"), contextFor(["coverage"]));

    expect(response.status).toBe(401);
    expect(response.headers.get("x-kis-degraded")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ["a wrong key of the same length", "proxy-server-kez"],
    ["a shorter key", "proxy"],
    ["a longer key", `${"proxy-server-key"}-extra`],
    ["an empty key", ""],
  ])("rejects %s without throwing on length", async (_label, presented) => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await GET(
      requestWithKey("/api/coverage", presented),
      contextFor(["coverage"]),
    );

    expect(response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("falls back to DASHBOARD_API_KEY when KIS_BUILDER_API_KEY is unset", async () => {
    delete process.env.KIS_BUILDER_API_KEY;
    process.env.DASHBOARD_API_KEY = "dashboard-only-key";
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ ok: true }));

    const rejected = await GET(requestFor("/api/coverage"), contextFor(["coverage"]));
    expect(rejected.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();

    const accepted = await GET(
      requestWithKey("/api/coverage", "dashboard-only-key"),
      contextFor(["coverage"]),
    );
    expect(accepted.status).toBe(200);
  });
});

describe("proxy with no key configured stays open, matching the dashboard", () => {
  // services/dashboard/app.py:206 installs APIKeyMiddleware only under
  // `require_auth and api_key`. With no key configured the dashboard enforces
  // nothing and this proxy attaches nothing, so enforcing here would break the
  // keyless dev setup without protecting anything.
  // No per-describe setup: the file-level hook already leaves both vars unset,
  // which is exactly the condition under test.
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("forwards an unauthenticated call and lends no key", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ ok: true }));

    const response = await GET(requestFor("/api/coverage"), contextFor(["coverage"]));

    expect(response.status).toBe(200);
    const forwarded = new Headers(fetchMock.mock.calls[0][1]?.headers as HeadersInit);
    expect(forwarded.has("X-API-Key")).toBe(false);
  });
});


// ---------------------------------------------------------------------------
// #861 review notes c (rear) and d — `tos` was a dedicated early return in
// targetPathFor(), outside both compatRoots and directRoots, so isDirectPath()
// disagreed with the path targetPathFor() actually produced; and HEAD was
// refused on the TOS projection while every other root proxied it.
//
// `tos` is now an ordinary direct root with an exact-path allowlist, and the
// GET-only rule is a property of the root rather than of one literal target.
//
// Deployment note: Caddy sends /api/tos* straight to dashboard:8001
// (caddy/Caddyfile @to_dashboard), so everything below is dev-server /
// defence-in-depth behaviour, not the deployed request path.
// ---------------------------------------------------------------------------
describe("TOS routing lives in the routing table", () => {
  afterEach(() => vi.restoreAllMocks());

  it("resolves the projection through the direct-root form, never a kis-builder rewrite", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ available: false }));

    const response = await GET(
      requestFor("/api/tos/projection"),
      contextFor(["tos", "projection"]),
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://localhost:5081/api/tos/projection",
    );
    expect(String(fetchMock.mock.calls[0][0])).not.toContain("/api/kis-builder/");
  });

  it.each([
    [["tos"], "/api/tos"],
    [["tos", "projection", "extra"], "/api/tos/projection/extra"],
    [["tos", "projection", ""], "/api/tos/projection/"],
    [["tos", "projection", "a", "b"], "/api/tos/projection/a/b"],
    [["tos", "rearm"], "/api/tos/rearm"],
    [["tos", "projections"], "/api/tos/projections"],
    [["tos", "PROJECTION"], "/api/tos/PROJECTION"],
  ])("refuses %s — the allowlist is exact, not a prefix", async (path, url) => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await GET(requestFor(url), contextFor(path as string[]));

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("does not turn ordinary direct roots into exact-path roots", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ ok: true }));

    const response = await GET(
      requestFor("/api/portfolio/equity/history?days=30"),
      contextFor(["portfolio", "equity", "history"]),
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://localhost:5081/api/portfolio/equity/history?days=30",
    );
  });

  it("answers an unknown path under the GET-only root as 404, not 405", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await POST(
      requestWithMethod("/api/tos/rearm", "POST"),
      contextFor(["tos", "rearm"]),
    );

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("TOS HEAD policy", () => {
  afterEach(() => vi.restoreAllMocks());

  // Decision: HEAD stays refused with 405, because the dashboard refuses it too.
  // services/dashboard/routes/tos_projection.py declares only
  // `@router.get("/projection")`, and FastAPI's APIRoute does not add HEAD to a
  // GET route the way Starlette's Route does — measured against the real router
  // with TestClient: GET 200, HEAD 405, POST 405. Proxying HEAD would spend a
  // round trip to return the dashboard's 405 anyway.
  it("refuses HEAD on the projection with the same 405 and Allow header as the other methods", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await GET(
      requestWithMethod("/api/tos/projection", "HEAD"),
      contextFor(["tos", "projection"]),
    );

    expect(response.status).toBe(405);
    expect(response.headers.get("Allow")).toBe("GET");
    expect(await response.json()).toEqual({ detail: "Read-only TOS endpoint" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("still proxies HEAD for every other root, bodyless", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));

    const response = await GET(
      requestWithMethod("/api/coverage?asset_class=futures", "HEAD"),
      contextFor(["coverage"]),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1]?.method).toBe("HEAD");
    expect(fetchMock.mock.calls[0][1]?.body).toBeUndefined();
  });

  it("serves the degraded HEAD fallback for a proxied root when upstream is offline", async () => {
    // degradedResponse() explicitly admits HEAD alongside GET; with tos the only
    // GET-only root, that branch is reachable rather than dead code.
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );

    const response = await GET(
      requestWithMethod("/api/coverage?asset_class=futures", "HEAD"),
      contextFor(["coverage"]),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("x-kis-degraded")).toBe("dashboard_api_unavailable");
  });
});
