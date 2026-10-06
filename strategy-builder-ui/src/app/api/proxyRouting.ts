// Routing table for the /api catch-all proxy (./[...path]/route.ts).
//
// It lives beside the route rather than inside it because a Next.js route
// module may export only the HTTP handlers and a fixed set of config keys —
// `next build` type-checks that shape (next-types-plugin's `checkFields<Diff<…>>`),
// so an extra named export there is a build error. Keeping the table here makes
// it importable by tests without that constraint, and makes targetPathFor()
// unit-testable on its own.

// Legacy upstream-Builder roots. These are rewritten to /api/kis-builder/<path>
// on the dashboard, which is where their handlers actually live.
export const compatRoots = new Set([
  "auth",
  "account",
  "orders",
  "market",
  "files",
  "symbols",
  "experiments",
]);

// STS-native roots, forwarded at their own path.
//
// Membership here, not in Caddy's `@to_dashboard` matcher, is what makes a root
// reachable from every entry point: Caddy's `handle {}` fallback sends
// everything unmatched to this proxy, and `next dev` (no Caddy) only ever
// reaches this proxy. A root served by Caddy alone 404s here — so a UI call
// site whose root is missing from this set is a 404 the backend never sees
// (commit 1a614f09, for market-risk/portfolio). uiCallSiteRoots.test.ts holds
// the two sides together.
export const directRoots = new Set([
  "analytics",
  "coverage",
  "event-context",
  "evidence",
  "health",
  "kis-builder",
  "market-data",
  "market-risk",
  "portfolio",
  "reports",
  "signals",
  "strategies",
  "strategy-builder",
  "strategy-lab",
  "tos",
  "trades",
  "trading",
]);

// Roots whose surface is an exact allowlist rather than a whole subtree.
// Anything else under the root is refused here instead of being forwarded, so
// adding a route to the dashboard never silently widens this proxy.
//
// `tos` used to be a dedicated early return in targetPathFor(), outside both
// routing sets — which meant isDirectPath() answered `false` for a path
// targetPathFor() was in fact sending to the direct `/api/<path>` form
// (#861 review note c). Latent, because targetPathFor() short-circuited before
// consulting isDirectPath(); the hazard was the next edit that trusted
// isDirectPath() and rewrote /api/tos/projection to /api/kis-builder/....
export const exactPathRoots = new Map<string, ReadonlySet<string>>([
  ["tos", new Set(["tos/projection"])],
]);

// Roots this proxy forwards only as GET. The dashboard's TOS surface is
// read-only: services/dashboard/routes/tos_projection.py declares
// `@router.get("/projection")` and nothing else, and FastAPI's APIRoute — unlike
// Starlette's Route — does not add HEAD to a GET route, so the dashboard itself
// answers 405 to HEAD and to every mutating method there. Refusing them here
// keeps the proxy's answer identical to the dashboard's instead of relaying a
// round trip that is guaranteed to fail.
export const getOnlyRoots = new Set(["tos"]);

export function isDirectPath(path: string[]): boolean {
  const root = path[0];
  if (!root) return false;
  if (root === "strategies") return path.length === 1;
  return directRoots.has(root);
}

export function targetPathFor(path: string[]): string | null {
  const root = path[0];
  // The allowlist is consulted before every per-root early return below.
  // Ordering is load-bearing: with this after the `strategies` arm, a
  // `strategies` entry in exactPathRoots would be silently ignored — the exact
  // shape (a root-specific early return short-circuiting the routing table)
  // that this module removed from `tos`. Compare the whole joined path, not a
  // prefix, so a trailing empty segment, a deeper path, or a differently cased
  // segment all fall through to null rather than reaching the dashboard.
  const allowedPaths = exactPathRoots.get(root);
  if (allowedPaths && !allowedPaths.has(path.join("/"))) {
    return null;
  }
  if (root === "strategies" && path.length > 1) {
    return `/api/kis-builder/${path.join("/")}`;
  }
  const isDirectRoot = isDirectPath(path);
  if (!root || (!compatRoots.has(root) && !isDirectRoot)) {
    return null;
  }
  return isDirectRoot
    ? `/api/${path.join("/")}`
    : `/api/kis-builder/${path.join("/")}`;
}
