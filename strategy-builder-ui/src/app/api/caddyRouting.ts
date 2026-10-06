// What Caddy sends straight to dashboard:8001, read from the deployed config.
//
// It lives beside proxyRouting.ts, and is read rather than copied, for the
// reason caddy/Caddyfile itself gives for keeping no copy of the proxy's lists:
// a second hand-maintained list drifts from the first, silently, because
// nothing fails when it does. Tests import this; the route module does not —
// the proxy never needs to know what Caddy matched, only what it can resolve.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const CADDYFILE = resolve(__dirname, "../../../../caddy/Caddyfile");

const DASHBOARD_UPSTREAM = /reverse_proxy\s+dashboard:/;

/** Comment lines carry example paths, so they must not be parsed as config. */
function withoutComments(caddyfile: string): string {
  return caddyfile
    .split("\n")
    .filter((line) => !/^\s*#/.test(line))
    .join("\n");
}

function apiRootsIn(text: string): string[] {
  return [...text.matchAll(/\/api\/([a-z0-9-]+)/g)].map((m) => m[1]);
}

/**
 * Bodies of every `<directive> <args> {` block, paired with their args.
 *
 * The Caddyfile nests one level deep inside the site block, and no block body
 * contains a `}` of its own on a `\t\t`-indented line, so matching to the first
 * `\n\t}` is enough. A deeper rewrite would break this, which the tests that
 * pin both routing forms would catch.
 */
function blocks(text: string): Array<{ args: string; body: string }> {
  return [...text.matchAll(/^\t(\S+)([^\n{]*)\{\n([\s\S]*?)\n\t\}/gm)].map((m) => ({
    args: `${m[1]} ${m[2]}`,
    body: m[3],
  }));
}

/**
 * The `/api/<root>` prefixes Caddy proxies to the dashboard itself.
 *
 * Two forms reach dashboard:8001 and both count — a path matcher written inline
 * on the directive (`handle /api/kis-builder/* { reverse_proxy dashboard:8001 }`)
 * and a named matcher the directive references (`@to_dashboard { path … }` with
 * `handle @to_dashboard { reverse_proxy dashboard:8001 }`). Reading only the
 * named one reports `kis-builder` as unreachable by Caddy, which is false.
 *
 * Roots only: these blocks also match non-/api paths (/health, /docs,
 * /openapi.json, /redoc, /metrics, /ws) that no routing table of the proxy's
 * covers, and they are not what any caller of this function asks about.
 */
export function caddyDirectRoots(): Set<string> {
  const config = withoutComments(readFileSync(CADDYFILE, "utf8"));
  const all = blocks(config);

  const namedMatchers = new Map<string, string[]>();
  for (const { args, body } of all) {
    const name = /^(@\S+)/.exec(args.trim());
    if (name) namedMatchers.set(name[1], apiRootsIn(body));
  }

  const roots = new Set<string>();
  for (const { args, body } of all) {
    if (!DASHBOARD_UPSTREAM.test(body)) continue;
    for (const root of apiRootsIn(args)) roots.add(root);
    for (const ref of args.match(/@\S+/g) ?? []) {
      for (const root of namedMatchers.get(ref) ?? []) roots.add(root);
    }
  }
  if (roots.size === 0) {
    throw new Error("caddy/Caddyfile: found no /api root proxied to dashboard");
  }
  return roots;
}
