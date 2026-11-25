import { createHash, timingSafeEqual } from "node:crypto";
import { NextRequest } from "next/server";

import { getOnlyRoots, targetPathFor } from "../proxyRouting";

const apiBase = process.env.KIS_BUILDER_API_BASE || "http://localhost:5081";

// Auth invariant (#861 review note f): this proxy attaches the server-side
// dashboard key to every upstream call, so it must not forward a request it has
// not itself authenticated — otherwise it is a credential-lending bypass of the
// dashboard's own APIKeyMiddleware (services/dashboard/middleware/auth.py).
// Caddy sends /api/tos* straight to dashboard:8001, so in the deployed stack
// this proxy is the `next dev` path and defence in depth; it authenticates
// anyway, because a root that is in `directRoots` and NOT in Caddy's matcher
// reaches the dashboard only through here, and such a root answered 200 with no
// key before this guard while the identical path 401'd on the dashboard.
//
// Enforced only when a key is configured, mirroring the dashboard, which
// installs its auth middleware under `require_auth and api_key`
// (services/dashboard/app.py). With no key configured nothing is attached and
// nothing upstream is protected, so there is still no keyed path left open.
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

// No degraded empty-state fallbacks live here any more. They existed for the
// legacy dashboard reads (health summary, trading status, coverage, event
// context, trades, signals, strategies, the Builder compat roots) so a page
// could render an explicit "unavailable" shape instead of an error; every one
// of those endpoints and pages is gone (legacy removal L4/L5). The one
// surviving read, /api/tos/projection, deliberately never had one: the TOS page
// must show a connection error with its last known values, never a fabricated
// snapshot, so an unreachable dashboard stays a 503 here.
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
  // — upstream behaviour, outside this guard (#861 note a).
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
    return Response.json(
      { detail: "Dashboard API unavailable", upstream_path: targetPath },
      { status: 503 },
    );
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
