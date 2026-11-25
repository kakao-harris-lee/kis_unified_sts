import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { DELETE, GET, POST, PUT } from "./[...path]/route";
import type { NextRequest } from "next/server";
import { caddyDirectRoots } from "./caddyRouting";
import { directRoots, exactPathRoots } from "./proxyRouting";

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

// ---------------------------------------------------------------------------
// One root is left (legacy removal L4/L5): `tos`, whose only path is the
// read-only projection. The degraded empty-state fallbacks this proxy used to
// serve for the legacy reads went with those endpoints, so an unreachable
// dashboard is a 503 here rather than a fabricated snapshot — which is what the
// TOS page needs, since it must distinguish "no new state" from "all clear".
// ---------------------------------------------------------------------------
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

  it("carries the query string through to the dashboard", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ available: false }));
    await GET(
      requestFor("/api/tos/projection?include=raw"),
      contextFor(["tos", "projection"]),
    );
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://localhost:5081/api/tos/projection?include=raw",
    );
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
    [["tos"], "/api/tos"],
    [["tos", "projection", "extra"], "/api/tos/projection/extra"],
    [["tos", "projection", ""], "/api/tos/projection/"],
    [["tos", "projection", "a", "b"], "/api/tos/projection/a/b"],
    [["tos", "rearm"], "/api/tos/rearm"],
    [["tos", "projections"], "/api/tos/projections"],
    [["tos", "PROJECTION"], "/api/tos/PROJECTION"],
  ])("refuses %s — the allowlist is exact, not a prefix", async (path, url) => {
    // Exercises the exactPathRoots allowlist in proxyRouting.ts: with that
    // lookup removed, every one of these proxies through as if it were the
    // projection.
    const fetchMock = vi.spyOn(globalThis, "fetch");
    const response = await GET(requestFor(url), contextFor(path as string[]));
    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
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

  it.each([401, 403, 404, 503])(
    "preserves upstream status %s instead of inventing an empty healthy snapshot",
    async (status) => {
      vi.spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ detail: "unavailable" }, { status }));
      const response = await GET(requestFor("/api/tos/projection"), contextFor(["tos", "projection"]));
      expect(response.status).toBe(status);
      expect(response.headers.get("x-kis-degraded")).toBeNull();
    },
  );

  it("reports network failure as 503, naming the upstream path", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      Object.assign(new Error("fetch failed"), { code: "ECONNREFUSED" }),
    );
    const response = await GET(requestFor("/api/tos/projection"), contextFor(["tos", "projection"]));
    const body = await response.json();
    expect(response.status).toBe(503);
    expect(response.headers.get("x-kis-degraded")).toBeNull();
    expect(body.upstream_path).toBe("/api/tos/projection");
  });
});

// ---------------------------------------------------------------------------
// Caddy proxies /api/tos* straight to dashboard:8001 AND the root is in this
// proxy's table, so both entry points reach the dashboard: the container
// through Caddy, `npm run dev` through here. The two lists are read, never
// copied, so neither this comment nor a hand-kept list has to stay in step.
// ---------------------------------------------------------------------------
describe("Caddy and the proxy routing table agree on the surviving root", () => {
  it("reads /api/tos out of the deployed Caddyfile as dashboard-bound", () => {
    expect([...caddyDirectRoots()].sort()).toEqual(["tos"]);
  });

  it("leaves no proxy-only root without an auth case in this file", () => {
    // Before L5 this difference was non-empty (analytics, coverage,
    // event-context, evidence, market-data, market-risk, portfolio, reports)
    // and each root needed its own 401/forwarding case below, because a root
    // reachable ONLY through this proxy is a root whose auth guard nothing else
    // exercises. The difference is empty now. A root added to directRoots
    // without a Caddyfile entry turns this red, which is the signal to add that
    // root's cases rather than to widen this assertion.
    const caddyDirect = caddyDirectRoots();
    expect([...directRoots].filter((root) => !caddyDirect.has(root))).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// #861 review note f — the proxy attaches the server-side dashboard key to
// every upstream call, so it must authenticate the caller first. Every browser
// caller already attaches X-API-Key from NEXT_PUBLIC_API_KEY
// (src/lib/dashboard/client.ts), so there is no public exception.
// ---------------------------------------------------------------------------
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

  it("rejects the projection with 401 when the caller presents no key", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await GET(
      requestFor("/api/tos/projection"),
      contextFor(["tos", "projection"]),
    );

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ detail: "Invalid or missing API key" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards the projection with the server key once the caller authenticates", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ ok: true }));

    const response = await GET(
      requestWithKey("/api/tos/projection", SERVER_KEY),
      contextFor(["tos", "projection"]),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const forwarded = new Headers(fetchMock.mock.calls[0][1]?.headers as HeadersInit);
    expect(forwarded.get("X-API-Key")).toBe(SERVER_KEY);
  });

  it.each(["POST", "PUT", "DELETE"] as const)(
    "rejects unauthenticated %s before reading the body",
    async (method) => {
      const fetchMock = vi.spyOn(globalThis, "fetch");
      const handler = { POST, PUT, DELETE }[method];
      const request = requestWithMethod("/api/tos/projection", method);
      const arrayBuffer = vi.fn(async () => new ArrayBuffer(0));
      (request as unknown as { arrayBuffer: () => Promise<ArrayBuffer> }).arrayBuffer =
        arrayBuffer;

      // 401, not the 405 a read-only root answers an authenticated mutation
      // with: the key check runs before the path and the method are resolved.
      const response = await handler(request, contextFor(["tos", "projection"]));

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

  it.each([
    ["a wrong key of the same length", "proxy-server-kez"],
    ["a shorter key", "proxy"],
    ["a longer key", `${"proxy-server-key"}-extra`],
    ["an empty key", ""],
  ])("rejects %s without throwing on length", async (_label, presented) => {
    const fetchMock = vi.spyOn(globalThis, "fetch");

    const response = await GET(
      requestWithKey("/api/tos/projection", presented),
      contextFor(["tos", "projection"]),
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

    const rejected = await GET(
      requestFor("/api/tos/projection"),
      contextFor(["tos", "projection"]),
    );
    expect(rejected.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();

    const accepted = await GET(
      requestWithKey("/api/tos/projection", "dashboard-only-key"),
      contextFor(["tos", "projection"]),
    );
    expect(accepted.status).toBe(200);
  });
});

describe("proxy with no key configured stays open, matching the dashboard", () => {
  // services/dashboard/app.py installs APIKeyMiddleware only under
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

    const response = await GET(
      requestFor("/api/tos/projection"),
      contextFor(["tos", "projection"]),
    );

    expect(response.status).toBe(200);
    const forwarded = new Headers(fetchMock.mock.calls[0][1]?.headers as HeadersInit);
    expect(forwarded.has("X-API-Key")).toBe(false);
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
});

// ---------------------------------------------------------------------------
// The routing table has one root today, so every property below would be
// vacuous if it were only exercised through `tos`. A second root is injected
// for the duration of each test instead — the same technique the `strategies`
// cases used before that root was deleted (#868 review finding 1), which is
// what keeps "the allowlist applies to every root" an assertion rather than a
// restatement of the tos entry.
// ---------------------------------------------------------------------------
describe("the routing rules are properties of the table, not of tos", () => {
  afterEach(() => {
    directRoots.delete("probe");
    exactPathRoots.delete("probe");
    vi.restoreAllMocks();
  });

  it("refuses a path outside a second root's allowlist entry", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ ok: true }));
    directRoots.add("probe");
    exactPathRoots.set("probe", new Set(["probe/allowed"]));

    const response = await GET(
      requestFor("/api/probe/other"),
      contextFor(["probe", "other"]),
    );

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("forwards that root's allowlisted path at its own /api path", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ ok: true }));
    directRoots.add("probe");
    exactPathRoots.set("probe", new Set(["probe/allowed"]));

    const response = await GET(
      requestFor("/api/probe/allowed"),
      contextFor(["probe", "allowed"]),
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://localhost:5081/api/probe/allowed",
    );
  });

  it("does not turn an ordinary direct root into an exact-path root", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(Response.json({ ok: true }));
    directRoots.add("probe");

    const response = await GET(
      requestFor("/api/probe/any/depth?days=30"),
      contextFor(["probe", "any", "depth"]),
    );

    expect(response.status).toBe(200);
    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://localhost:5081/api/probe/any/depth?days=30",
    );
  });

  it("proxies HEAD for a root that is not GET-only, bodyless", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 200 }));
    directRoots.add("probe");

    const response = await GET(
      requestWithMethod("/api/probe/status", "HEAD"),
      contextFor(["probe", "status"]),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1]?.method).toBe("HEAD");
    expect(fetchMock.mock.calls[0][1]?.body).toBeUndefined();
  });
});
