/**
 * Reachability guardrail for every same-origin /api call site in the UI.
 *
 * This app has two same-origin API clients, and both reach the same proxy:
 * src/lib/dashboard/client.ts (axios, empty baseURL) and src/lib/api/client.ts
 * (fetch, empty baseURL — its own head comment says the catch-all proxy
 * rewrites its paths). Harvesting one of them leaves the other free to add an
 * unroutable path: a scratch `apiGet("/api/screener/latest")` in
 * src/lib/api/experiments.ts passed this file while the proxy 404'd it. Both
 * trees are walked recursively, so a call site in a subdirectory is covered
 * too. `builder-ui-two-api-clients-auth` records the same two-client trap.
 *
 * In the deployed stack an /api path is served either by Caddy's
 * `@to_dashboard` matcher (straight to dashboard:8001) or by the Next
 * catch-all proxy's routing table (src/app/api/proxyRouting.ts), which is what
 * Caddy's `handle {}` fallback reaches. A path in neither place answers 404
 * from the proxy with `{"detail":"Unsupported Strategy Builder API path"}` —
 * the defect commit 1a614f09 fixed for `market-risk`/`portfolio` and this file
 * prevents from recurring. Frontend unit tests mock both clients, so nothing
 * else in the suite exercises the real routing for a new call site.
 *
 * The asserted property is the stronger of the two: every call site must
 * resolve through `targetPathFor`, not merely appear in one of the two lists.
 * Caddy membership alone is not reachability — `next dev` (npm run dev, the
 * documented frontend workflow) serves the UI on :3100 with no Caddy in front,
 * so a root reachable only via `@to_dashboard` 404s there. The concrete input
 * this rejects and a union-of-both-lists check would accept: adding
 * `path /api/analytics /api/analytics/*` to caddy/Caddyfile instead of adding
 * `analytics` to `directRoots`.
 *
 * The Caddyfile is still parsed, to say in the failure message whether the
 * unresolvable root is Caddy-direct (works in the container, 404s under
 * `next dev`) or reaches nothing at all.
 */

import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { relative, resolve } from "node:path";

import { targetPathFor } from "./proxyRouting";

// Both same-origin API client trees. Neither is more authoritative than the
// other: a path added under either one is served by the same proxy.
const CLIENT_LIB_DIRS = [
  resolve(__dirname, "../../lib/dashboard"),
  resolve(__dirname, "../../lib/api"),
];
const CADDYFILE = resolve(__dirname, "../../../../caddy/Caddyfile");

/** A dynamic `${...}` segment stands in for any single path segment. */
const DYNAMIC_SEGMENT = "__dynamic__";

/** Every non-test `.ts` file under `dir`, at any depth. */
function sourceFilesUnder(dir: string): string[] {
  const files: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = resolve(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...sourceFilesUnder(full));
    } else if (entry.name.endsWith(".ts") && !entry.name.endsWith(".test.ts")) {
      files.push(full);
    }
  }
  return files;
}

/** `/api/...` paths the UI's API clients request, by source file. */
function callSitePaths(): Array<{ file: string; apiPath: string }> {
  const found: Array<{ file: string; apiPath: string }> = [];
  for (const dir of CLIENT_LIB_DIRS) {
    for (const full of sourceFilesUnder(dir)) {
      const source = readFileSync(full, "utf8");
      // Quoted or backticked literals starting with /api/, up to the closing
      // quote. Template holes are substituted, not matched.
      for (const match of source.matchAll(/['"`](\/api\/[^'"`]*)['"`]?/g)) {
        found.push({
          file: relative(resolve(__dirname, "../.."), full),
          apiPath: match[1].replace(/\$\{[^}]*\}/g, DYNAMIC_SEGMENT),
        });
      }
    }
  }
  return found;
}

/** `/api/<root>` prefixes Caddy sends straight to dashboard:8001. */
function caddyDirectRoots(): Set<string> {
  const caddyfile = readFileSync(CADDYFILE, "utf8");
  const matcher = /@to_dashboard\s*\{([\s\S]*?)\n\t\}/.exec(caddyfile);
  if (!matcher) throw new Error("caddy/Caddyfile has no @to_dashboard matcher block");
  const roots = new Set<string>();
  for (const line of matcher[1].matchAll(/^\s*path\s+(.*)$/gm)) {
    for (const token of line[1].split(/\s+/)) {
      const root = /^\/api\/([a-z0-9-]+)/.exec(token);
      if (root) roots.add(root[1]);
    }
  }
  return roots;
}

/**
 * Path segments `targetPathFor` would receive for this literal — the query
 * string and fragment dropped, since Next hands the route only `params.path`
 * and the proxy carries the search string separately (`target.search =
 * request.nextUrl.search`).
 */
function segmentsOf(apiPath: string): string[] {
  return apiPath
    .replace(/[?#].*$/, "")
    .replace(/^\/api\/?/, "")
    .split("/")
    .filter(Boolean);
}

describe("every same-origin API call site is reachable through the deployed stack", () => {
  it("finds the call sites it is meant to guard", () => {
    const paths = callSitePaths();
    // A regex that silently matched nothing would make every assertion below
    // vacuously true, so pin the shape of the harvest itself.
    expect(paths.length).toBeGreaterThan(90);
    // One pin per client tree, so dropping either one is red rather than a
    // smaller number nobody reads.
    expect(paths.map((p) => p.apiPath)).toContain("/api/trades/statistics");
    expect(paths.map((p) => p.apiPath)).toContain(
      `/api/signals/${DYNAMIC_SEGMENT}/trace`,
    );
    expect(paths.map((p) => p.file)).toContain("lib/dashboard/trades.ts");
    expect(paths.map((p) => p.file)).toContain("lib/api/symbols.ts");
  });

  // A literal may carry its own query string or fragment — src/lib/api/
  // symbols.ts builds `/api/symbols/search?${params}`. Those belong to the
  // request, not to the path, and `targetPathFor` is given segments only. Left
  // attached they ride along on the last segment, which the exact-path
  // allowlist compares whole: "tos/projection?include=foo" is not
  // "tos/projection", so a path the proxy resolves fine would be reported as
  // reaching no hop at all.
  it.each([
    ["/api/tos/projection", ["tos", "projection"]],
    ["/api/tos/projection?include=foo", ["tos", "projection"]],
    ["/api/tos/projection#anchor", ["tos", "projection"]],
    [`/api/symbols/search?${DYNAMIC_SEGMENT}`, ["symbols", "search"]],
  ])("segments %s without its query or fragment", (apiPath, expected) => {
    expect(segmentsOf(apiPath)).toEqual(expected);
    expect(targetPathFor(segmentsOf(apiPath))).not.toBeNull();
  });

  it("resolves every call site through the catch-all proxy routing table", () => {
    const caddyDirect = caddyDirectRoots();
    const unresolved = callSitePaths()
      .filter(({ apiPath }) => targetPathFor(segmentsOf(apiPath)) === null)
      .map(({ file, apiPath }) => {
        const root = segmentsOf(apiPath)[0];
        const hop = caddyDirect.has(root)
          ? "Caddy-direct only — 404s under `next dev`, which has no Caddy"
          : "no hop at all — 404 everywhere";
        return `${file}: ${apiPath} (root "${root}": ${hop})`;
      });

    expect(unresolved).toEqual([]);
  });
});
