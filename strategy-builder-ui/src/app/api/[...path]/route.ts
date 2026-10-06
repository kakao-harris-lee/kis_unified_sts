import { createHash, timingSafeEqual } from "node:crypto";
import { NextRequest } from "next/server";

import { getOnlyRoots, targetPathFor } from "../proxyRouting";

const apiBase = process.env.KIS_BUILDER_API_BASE || "http://localhost:5081";

// Auth invariant (#861 review note f): this proxy attaches the server-side
// dashboard key to every upstream call, so it must not forward a request it has
// not itself authenticated — otherwise it is a credential-lending bypass of the
// dashboard's own APIKeyMiddleware (services/dashboard/middleware/auth.py).
// Caddy sends most /api roots straight to dashboard:8001, but coverage,
// event-context, market-risk, portfolio and reports reach the dashboard only
// through here, so without this guard those five answered 200 with no key while
// the identical paths 401'd when called on the dashboard directly.
//
// Enforced only when a key is configured, mirroring the dashboard, which
// installs its auth middleware under `require_auth and api_key`
// (services/dashboard/app.py:206). With no key configured nothing is attached
// and nothing upstream is protected, so there is still no keyed path left open.
function configuredApiKey(): string {
  return process.env.KIS_BUILDER_API_KEY || process.env.DASHBOARD_API_KEY || "";
}

// Digest both sides before comparing so the fixed-width compare does not reject
// on length (timingSafeEqual throws on unequal buffers) and does not leak the
// configured key's length through an early return.
function apiKeyMatches(presented: string | null, expected: string): boolean {
  if (!presented || !expected) return false;
  return timingSafeEqual(
    createHash("sha256").update(presented).digest(),
    createHash("sha256").update(expected).digest(),
  );
}

export const dynamic = "force-dynamic";

type RouteContext = {
  params: { path?: string[] } | Promise<{ path?: string[] }>;
};

function requestedAsset(request: NextRequest): "stock" | "futures" | "all" {
  const asset = request.nextUrl.searchParams.get("asset_class");
  return asset === "stock" || asset === "futures" || asset === "all" ? asset : "all";
}

function unavailableNote(targetPath: string): string {
  return `Dashboard API unavailable for ${targetPath}; showing local degraded empty state.`;
}

function degradedJson(body: unknown): Response {
  return Response.json(body, {
    headers: { "x-kis-degraded": "dashboard_api_unavailable" },
  });
}

function zeroTradeStats() {
  return {
    total_trades: 0,
    winning_trades: 0,
    losing_trades: 0,
    win_rate: 0,
    total_pnl: 0,
    avg_pnl: 0,
    max_win: 0,
    max_loss: 0,
    profit_factor: 0,
  };
}

function degradedRiskExposure(asset: "stock" | "futures" | "all", targetPath: string) {
  const now = new Date().toISOString();
  return {
    asset_class: asset,
    generated_at: now,
    portfolio: {
      equity_krw: null,
      cash_krw: null,
      gross_exposure_krw: 0,
      net_exposure_krw: 0,
      unrealized_pnl_krw: 0,
      realized_pnl_krw: null,
      daily_pnl_krw: 0,
      daily_loss_krw: 0,
      open_positions: 0,
      exposure_to_equity_pct: null,
      last_update: now,
    },
    by_strategy: [],
    by_symbol: [],
    notes: [unavailableNote(targetPath)],
  };
}

function degradedHealthSummary(asset: "stock" | "futures" | "all", targetPath: string) {
  const now = new Date().toISOString();
  const killSwitch = { enabled: false, active_conditions: [] };
  const degradedProcess = {
    asset_class: asset,
    name: "dashboard_api",
    alive: false,
    status: "degraded",
  };
  const degradedDataSource = {
    asset_class: asset,
    name: "dashboard_api",
    fresh_ratio: 0,
    status: "degraded",
  };
  return {
    processes: [degradedProcess],
    data_sources: [degradedDataSource],
    kill_switch: killSwitch,
    today_pnl: 0,
    asset_class: asset,
    checked_at: now,
    ops_summary: {
      asset_class: asset,
      as_of: now,
      mode: { trading_mode: "unknown", real_trading: false },
      health: {
        dashboard: "degraded",
        redis: "degraded",
        runtime_ledger: "degraded",
        scheduler: "unknown",
        producers: "unknown",
      },
      data_freshness: {
        ticks_age_seconds: null,
        daily_indicators_age_seconds: null,
        universe_age_seconds: null,
      },
      forecasting: { har_rv_age_seconds: null, stale: true },
      kill_switch: killSwitch,
      pipeline: {
        stock_pipeline_mode: "unknown",
        futures_f9_state: "unknown",
      },
      pnl: {
        today_pnl_krw: 0,
        realized_pnl_krw: null,
        unrealized_pnl_krw: null,
      },
      notes: [unavailableNote(targetPath)],
    },
    scheduler: { status: "unknown" },
    producers: { status: "unknown" },
    forecasting: { stale: true },
    pipeline: {
      stock_pipeline_mode: "unknown",
      futures_f9_state: "unknown",
    },
    mode: { trading_mode: "unknown", real_trading: false },
  };
}

function degradedCoverage(asset: "stock" | "futures" | "all", targetPath: string) {
  return {
    asset_class: asset,
    generated_at: new Date().toISOString(),
    sources: [],
    experiment_coverage: [],
    missing_evidence: ["dashboard_api"],
    notes: [unavailableNote(targetPath)],
  };
}

function degradedEventContext(asset: "stock" | "futures" | "all", targetPath: string) {
  return {
    asset_class: asset,
    generated_at: new Date().toISOString(),
    event_scores: {
      latest_score_at: null,
      age_seconds: null,
      total_count: null,
      recent_count: null,
      sparsity_ratio: null,
      sparse: false,
      status: "unknown",
      by_source: [],
      by_impact_tier: {},
      warnings: ["dashboard_api_unavailable"],
    },
    source_timeline: [],
    setup_c: {
      strategy: "setup_c_event_reaction",
      enabled: null,
      window_minutes: null,
      min_impact_tier: null,
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
    missing_evidence: ["dashboard_api"],
    notes: [unavailableNote(targetPath)],
  };
}

function degradedTradingStatus(asset: "stock" | "futures" | "all", targetPath: string) {
  return {
    asset_class: asset,
    is_running: false,
    account: null,
    positions: [],
    message: unavailableNote(targetPath),
  };
}

function degradedLifecycle(asset: "stock" | "futures" | "all", targetPath: string, request: NextRequest) {
  const filters = Object.fromEntries(request.nextUrl.searchParams.entries());
  return {
    asset_class: asset,
    as_of: new Date().toISOString(),
    filters,
    lineage: {
      signal_id: filters.signal_id ?? null,
      order_id: filters.order_id ?? null,
      fill_id: filters.fill_id ?? null,
      trade_id: filters.trade_id ?? null,
      position_id: null,
    },
    steps: [
      {
        stage: "lifecycle",
        label: "Lifecycle",
        status: "unknown",
        id: null,
        timestamp: null,
        source: "not_available",
        summary: unavailableNote(targetPath),
        details: {},
      },
    ],
    warnings: ["dashboard_api_unavailable"],
  };
}

function degradedSignalTrace(asset: "stock" | "futures" | "all", targetPath: string, signalId: string) {
  return {
    signal: {
      id: signalId,
      asset_class: asset,
      symbol: "",
      strategy: "",
      side: "",
      signal_type: null,
      status: null,
      reason: null,
      confidence: null,
      strength: null,
      price: null,
      timestamp: null,
    },
    summary: {
      state: "unknown",
      text: unavailableNote(targetPath),
      warnings: ["dashboard_api_unavailable"],
    },
    llm_context: { status: "unknown" },
    strategy_inputs: {
      setup_type: null,
      indicators: {},
      thresholds: {},
      event_evidence: {},
      raw_reason: null,
    },
    risk_orderability: {
      reject_stage: null,
      reject_reason: null,
      orderability_state: null,
      orderability_details: {},
      risk_state: null,
      risk_details: {},
    },
    lineage: {
      signal_id: signalId,
      order_id: null,
      fill_id: null,
      position_id: null,
      trade_id: null,
    },
    lifecycle: {
      status: "not_available",
      steps: [],
      warnings: ["dashboard_api_unavailable"],
    },
    scorecard: {
      status: "unknown",
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
    evidence_gaps: [
      {
        code: "dashboard_api_unavailable",
        severity: "warning",
        message: unavailableNote(targetPath),
      },
    ],
  };
}

function degradedExperimentComparison(targetPath: string) {
  return {
    generated_at: new Date().toISOString(),
    source: {
      experiment_id: null,
      experiment_generated_at: null,
      ledger_available: false,
      min_paper_trades: 0,
    },
    comparisons: [],
    missing_evidence: ["dashboard_api"],
    notes: [unavailableNote(targetPath)],
  };
}

function degradedExperimentJob(targetPath: string, request: NextRequest) {
  const parts = request.nextUrl.pathname.split("/");
  return {
    job_id: parts[parts.length - 1] || "unknown",
    status: "failed",
    created_at: new Date().toISOString(),
    started_at: null,
    finished_at: new Date().toISOString(),
    error: unavailableNote(targetPath),
    experiment_id: null,
    report: null,
  };
}

function degradedResponse(path: string[], targetPath: string, request: NextRequest): Response | null {
  if (request.method !== "GET" && request.method !== "HEAD") return null;

  const asset = requestedAsset(request);
  const [root, second, third] = path;
  const page = Number(request.nextUrl.searchParams.get("page") || "1");
  const limit = Number(request.nextUrl.searchParams.get("limit") || "50");
  const days = Number(request.nextUrl.searchParams.get("days") || "7");

  if (root === "auth" && second === "status") {
    return degradedJson({
      authenticated: false,
      mode: "vps",
      mode_display: "Paper",
      can_switch_mode: true,
      cooldown_remaining: 0,
      unavailable: true,
    });
  }
  if (root === "health" && second === "summary") {
    return degradedJson(degradedHealthSummary(asset, targetPath));
  }
  if (root === "trading" && second === "risk-exposure") {
    return degradedJson(degradedRiskExposure(asset, targetPath));
  }
  if (root === "trading" && second === "status") {
    return degradedJson(degradedTradingStatus(asset, targetPath));
  }
  if (root === "trading" && second === "positions") {
    return degradedJson([]);
  }
  if (root === "coverage" && !second) {
    return degradedJson(degradedCoverage(asset, targetPath));
  }
  if (root === "event-context" && second === "diagnostics") {
    return degradedJson(degradedEventContext(asset, targetPath));
  }
  if (root === "kis-builder" && second === "strategies") {
    return degradedJson({ strategies: [], notes: [unavailableNote(targetPath)] });
  }
  if (root === "kis-builder" && second === "registered" && third === "activity") {
    return degradedJson({ activity: [], notes: [unavailableNote(targetPath)] });
  }
  if (root === "kis-builder" && second === "registered") {
    return degradedJson({ strategies: [], total: 0, notes: [unavailableNote(targetPath)] });
  }
  if (root === "experiments" && second === "strategies") {
    return degradedJson({ strategies: [], notes: [unavailableNote(targetPath)] });
  }
  if (root === "experiments" && second === "latest" && third === "compare-paper") {
    return degradedJson(degradedExperimentComparison(targetPath));
  }
  if (root === "experiments" && second === "latest") {
    return degradedJson({ report: null, notes: [unavailableNote(targetPath)] });
  }
  if (root === "experiments" && second === "jobs") {
    return degradedJson(degradedExperimentJob(targetPath, request));
  }
  if (root === "signals" && !second) {
    return degradedJson({ signals: [], total: 0, asset_class: asset, notes: [unavailableNote(targetPath)] });
  }
  if (root === "signals" && second && third === "trace") {
    return degradedJson(degradedSignalTrace(asset, targetPath, second));
  }
  if (root === "signals" && second === "history") {
    return degradedJson({ history: [], total_signals: 0, days, notes: [unavailableNote(targetPath)] });
  }
  if (root === "trades" && !second) {
    return degradedJson({ trades: [], total: 0, page, limit, notes: [unavailableNote(targetPath)] });
  }
  if (root === "trades" && second === "statistics") {
    return degradedJson({ ...zeroTradeStats(), notes: [unavailableNote(targetPath)] });
  }
  if (root === "trades" && second === "by-strategy") {
    return degradedJson([]);
  }
  if (root === "trades" && second === "lifecycle") {
    return degradedJson(degradedLifecycle(asset, targetPath, request));
  }
  if (root === "trades" && second === "closed" && third === "statistics") {
    return degradedJson({ ...zeroTradeStats(), notes: [unavailableNote(targetPath)] });
  }
  if (root === "trades" && second === "closed") {
    return degradedJson([]);
  }
  if (root === "trades" && second === "fills") {
    return degradedJson({ fills: [], notes: [unavailableNote(targetPath)] });
  }
  if (root === "strategies" && !second) {
    return degradedJson({ strategies: [], total: 0, asset_class: asset, notes: [unavailableNote(targetPath)] });
  }

  return null;
}

function pathForFallback(targetPath: string): string[] {
  return targetPath.replace(/^\/api\/?/, "").split("/").filter(Boolean);
}

async function proxyBuilderApi(request: NextRequest, context: RouteContext): Promise<Response> {
  // Authenticate before resolving the path, so an unauthenticated caller cannot
  // use the 404-vs-401 split to enumerate which roots this proxy forwards.
  const serverApiKey = configuredApiKey();
  if (serverApiKey && !apiKeyMatches(request.headers.get("X-API-Key"), serverApiKey)) {
    // Same body the dashboard's middleware returns, so a client sees one shape
    // regardless of which hop rejected it.
    return Response.json({ detail: "Invalid or missing API key" }, { status: 401 });
  }

  const { path = [] } = await context.params;
  const targetPath = targetPathFor(path);
  if (!targetPath) {
    return Response.json({ detail: "Unsupported Strategy Builder API path" }, { status: 404 });
  }

  // Checked after path resolution, so an unknown path under a GET-only root is
  // still a 404 (unsupported) rather than a 405 (wrong method). OPTIONS never
  // gets here: Next answers it itself with 204 and an Allow header listing every
  // method, so a read-only root still advertises mutating ones on the dev server
  // — upstream behaviour, identical on main, outside this guard (#861 note a).
  if (getOnlyRoots.has(path[0]) && request.method !== "GET") {
    return Response.json({ detail: "Read-only TOS endpoint" }, { status: 405, headers: { Allow: "GET" } });
  }

  const target = new URL(targetPath, apiBase);
  target.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  headers.set("accept", "application/json");
  if (serverApiKey) headers.set("X-API-Key", serverApiKey);

  const body =
    request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.arrayBuffer();

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      redirect: "manual",
    });
  } catch {
    const degraded =
      degradedResponse(path, targetPath, request) ??
      degradedResponse(pathForFallback(targetPath), targetPath, request);
    if (degraded) return degraded;
    return Response.json(
      { detail: "Dashboard API unavailable", upstream_path: targetPath },
      { status: 503 },
    );
  }

  if (
    (request.method === "GET" || request.method === "HEAD") &&
    (upstream.status === 404 || upstream.status >= 500)
  ) {
    const degraded =
      degradedResponse(path, targetPath, request) ??
      degradedResponse(pathForFallback(targetPath), targetPath, request);
    if (degraded) return degraded;
  }

  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  responseHeaders.delete("transfer-encoding");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyBuilderApi(request, context);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyBuilderApi(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyBuilderApi(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<Response> {
  return proxyBuilderApi(request, context);
}
