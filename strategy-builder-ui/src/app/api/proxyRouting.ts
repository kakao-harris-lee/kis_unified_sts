// Routing table for the /api catch-all proxy (./[...path]/route.ts).
//
// It lives beside the route rather than inside it because a Next.js route
// module may export only the HTTP handlers and a fixed set of config keys —
// `next build` type-checks that shape (next-types-plugin's `checkFields<Diff<…>>`),
// so an extra named export there is a build error. Keeping the table here makes
// it importable by tests without that constraint, and makes targetPathFor()
// unit-testable on its own.
//
// One root is left. `compatRoots` — the legacy upstream-Builder roots (auth,
// account, orders, market, files, symbols, experiments) rewritten to
// /api/kis-builder/<path> — went with the dashboard handlers behind them
// (legacy removal L4) and the pages that called them (L5).

// STS-native roots, forwarded at their own path.
//
// Membership here, not in Caddy's `@to_dashboard` matcher, is what makes a root
// reachable from every entry point: Caddy's `handle {}` fallback sends
// everything unmatched to this proxy, and `next dev` (no Caddy) only ever
// reaches this proxy. A root served by Caddy alone 404s here — so a UI call
// site whose root is missing from this set is a 404 the backend never sees
// (commit 1a614f09, for market-risk/portfolio). uiCallSiteRoots.test.ts holds
// the two sides together.
export const directRoots = new Set(["tos"]);

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

// The same allowlist discipline for a surface that carries one caller-supplied
// segment. `*` matches EXACTLY ONE non-empty segment, so the pattern widens the
// proxy by one path shape and nothing else: `tos/sessions/<id>/bars` resolves,
// while `tos/sessions`, `tos/sessions/<id>`, `tos/sessions/<id>/bars/extra` and
// `tos/sessions//bars` all still reach null.
//
// A pattern rather than a prefix on purpose. `startsWith("tos/sessions/")`
// would forward every future path under that prefix the moment the dashboard
// grew one, which is the silent widening `exactPathRoots` exists to prevent.
// The segment is also validated on the other side
// (services/dashboard/routes/tos_bars.py matches it against a positive
// pattern), so a traversal attempt fails twice rather than once.
export const patternPathRoots = new Map<string, readonly string[]>([
  ["tos", ["tos/sessions/*/bars"]],
]);

/** Whether `path` matches `pattern`, with `*` standing for one non-empty segment. */
export function matchesPathPattern(path: string[], pattern: string): boolean {
  const parts = pattern.split("/");
  if (parts.length !== path.length) return false;
  return parts.every((part, index) =>
    part === "*" ? path[index].length > 0 : part === path[index],
  );
}

// Roots this proxy forwards only as GET. The dashboard's TOS surface is
// read-only: services/dashboard/routes/tos_projection.py declares
// `@router.get("/projection")` and tos_bars.py declares
// `@router.get("/sessions/{session_id}/bars")`, and nothing else, and
// FastAPI's APIRoute — unlike
// Starlette's Route — does not add HEAD to a GET route, so the dashboard itself
// answers 405 to HEAD and to every mutating method there. Refusing them here
// keeps the proxy's answer identical to the dashboard's instead of relaying a
// round trip that is guaranteed to fail.
export const getOnlyRoots = new Set(["tos"]);

export function isDirectPath(path: string[]): boolean {
  const root = path[0];
  if (!root) return false;
  return directRoots.has(root);
}

export function targetPathFor(path: string[]): string | null {
  const root = path[0];
  if (!root) return null;
  // The allowlist is consulted first, before any per-root handling. Ordering
  // was load-bearing while `strategies` had its own early return below: an
  // entry here for that root was silently ignored (#868 review finding 1), the
  // same root-specific short-circuit this module removed from `tos`. The early
  // return is gone with the compat roots, and the lookup stays first so the
  // next one added cannot reintroduce it. Compare the whole joined path, not a
  // prefix, so a trailing empty segment, a deeper path, or a differently cased
  // segment all fall through to null rather than reaching the dashboard.
  const allowedPaths = exactPathRoots.get(root);
  const allowedPatterns = patternPathRoots.get(root);
  if (allowedPaths || allowedPatterns) {
    const joined = path.join("/");
    const allowed =
      (allowedPaths?.has(joined) ?? false) ||
      (allowedPatterns?.some((pattern) => matchesPathPattern(path, pattern)) ?? false);
    if (!allowed) return null;
  }
  if (!isDirectPath(path)) {
    return null;
  }
  return `/api/${path.join("/")}`;
}
