# Vite Dashboard → Next.js Migration Plan

**Status**: ✅ DONE (2026-05-31) — phases 0–5 shipped (PRs #346, #350, #353, #355, #359–#361). Residual cleanup tracked in docs/superpowers/specs/2026-05-31-nextjs-consolidation-cleanup-design.md.
**Owner**: operator
**Driver**: PR introducing Caddy 5080 (this PR) — consolidates two web entries
behind one external port. Long-term goal is one codebase for the whole UI.

## Why migrate

Today two front-ends ship the dashboard:

| App | Stack | Port | Owner of route |
|---|---|---|---|
| `dashboard-frontend/` | Vite + React + React Router | dashboard:8001 | Cockpit, Positions, Signals, Trades, StrategyLab, **/builder (legacy)** |
| `strategy-builder-ui/` | Next.js (App Router) | strategy-builder-ui:3100 | /builder (canonical KIS upstream import), /execute |

After Caddy 5080 unification:

- `/builder*`, `/execute`, `/_next/*`, `/api/kis-builder/*` are routed to Next.js.
- Everything else is routed to the Vite SPA + FastAPI.
- The Vite SPA still ships a `/builder` route (`StrategyBuilder.tsx`) that is
  **dead code** under the new routing — it is never reached because Caddy
  intercepts `/builder` first.

Maintaining two SPAs is the largest source of operational drift in this repo
(per the 2026-05-28 audit: `5d45c18 feat: integrate kis strategy builder ui`
never made it to `origin/main` until this PR cherry-picked it). Consolidating
on Next.js gets us:

- One toolchain (`bun`, `next`), one dep graph, one lockfile.
- One auth context, one API client, one routing system.
- Server Components for the data-heavy pages (positions/trades) — strictly
  cheaper than client-side React Query for tables that don't need streaming.
- Upstream `koreainvestment/open-trading-api` strategy_builder lives on
  Next.js, so future upstream pulls become trivial.

## Phases

### Phase 0 — preconditions (this PR)

- [x] Restore `strategy-builder-ui/` source to `origin/main` (cherry-pick
      `5d45c18`).
- [x] `caddy/Caddyfile` routes `/builder`, `/execute`, `/_next/*`,
      `/api/kis-builder/*` to strategy-builder-ui; everything else to
      dashboard.
- [x] `docker-compose.yml` adds `caddy:` service bound to host `:5080`.
- [x] `dashboard-frontend/index.html` carries the `crypto.randomUUID`
      polyfill (#345) so HTTP-only `:5080` deployments work without an
      HTTPS cert.

### Phase 1 — neutralize the duplicate `/builder` in Vite SPA

After Phase 0 ships:

- Remove `dashboard-frontend/src/pages/StrategyBuilder.tsx`.
- Remove the corresponding route from `dashboard-frontend/src/App.tsx`.
- Remove any nav link to `/builder` (keep the same link target — Caddy
  routes it correctly).
- Validate locally with `bun run build` then a smoke test of `/builder`
  (must hit Next.js, NOT 404 from the Vite shell).

Small PR, low risk. Mark Vite `/builder` officially dead.

### Phase 2 — pick one shared design system

Inventory both apps:

- **Vite SPA** uses Tailwind + a small set of Radix-style primitives in
  `dashboard-frontend/src/components/ui/`.
- **Next.js** uses Tailwind + lucide-react icons and pieces of upstream's
  primitives in `strategy-builder-ui/src/components/ui/`.

Decision: keep the Next.js primitives (upstream-aligned). Port any
dashboard-specific tokens (color palette, spacing scale) into
`strategy-builder-ui/tailwind.config.ts` so existing dashboard pages can be
moved without restyling.

### Phase 3 — port pages one at a time

Order chosen for minimal blast radius:

| # | Page | Notes |
|---|---|---|
| 1 | `Cockpit` | Heaviest data dependence (positions, signals, fills). Land first so the rest can reuse its data hooks. |
| 2 | `Positions`, `Signals`, `Trades` | Drill-down pages; share data hooks with Cockpit. |
| 3 | `StrategyLab` | Standalone analysis UI; only depends on backtest API. |

Per page:

1. Create the equivalent Next.js route under `strategy-builder-ui/src/app/`.
2. Move the API client calls from
   `dashboard-frontend/src/api/` → `strategy-builder-ui/src/lib/api/`.
   Where the Next.js app already has an API helper for the same endpoint,
   merge them; otherwise port verbatim.
3. Move components from `dashboard-frontend/src/components/` →
   `strategy-builder-ui/src/components/`.
4. Update `caddy/Caddyfile`: add the new path under the Next.js handler
   block. Leave the old Vite route in place until the cutover step.
5. Smoke test both: old path on Vite still works; new path on Next.js
   matches.
6. Cutover: move the path to the Next.js handler in Caddyfile only — no
   Vite changes yet. (Two systems serving the same path is fine for an
   afternoon; one of them is the real one.)
7. Once stable, delete the Vite version.

### Phase 4 — remove the Vite SPA

When the last Vite page is ported:

- Delete `dashboard-frontend/`.
- Remove the static mount in `services/dashboard/app.py`.
- Remove the Vite default-route handler in `caddy/Caddyfile` — Next.js
  becomes the catch-all.
- The FastAPI dashboard keeps its `/api/*` namespace and its `/health`
  endpoint; it stops serving HTML.

### Phase 5 — production Next.js build

Today the strategy-builder-ui container runs `next dev` (set in
`Dockerfile.strategy_builder_ui`). For production stability:

- Add `next build` + `next start` to the Dockerfile (multi-stage to keep
  the image small).
- Disable `next dev`'s HMR/turbopack, which currently inflates memory
  usage and emits dev-only assets.
- Update healthcheck.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Auth context divergence between SPAs | Phase 2 lands one shared `AuthContext`; phase 3 page ports inherit it. |
| API client signatures drift | Port endpoints page-by-page; integration tests on the dashboard backend still pass against unchanged URLs. |
| Lost telemetry (Vite dashboard's own metrics) | Re-implement on the Next.js side as part of phase 3 for the first ported page (Cockpit). |
| Next.js dev server runs in production | Phase 5 switches to `next start`. Until then, container is `next dev` which is acceptable for an internal tool but should not stay long-term. |

## Out of scope

- HTTPS termination — the operator constraint allows only `:5080`
  externally. A later PR explores DNS-01-challenge cert via Caddy and
  a wildcard cert for the duckdns.org subdomain.
- Auth hardening — current setup uses `DASHBOARD_API_KEY` as a shared
  secret. Not changed by this migration.
- Mobile app — out of scope.

## Decision log

- **2026-05-28**: Operator asks for unification under one external port
  (`:5080`). Caddy chosen over nginx for simpler config and built-in
  Let's Encrypt for the future HTTPS path. Vite → Next.js consolidation
  chosen over Next.js → Vite because upstream KIS strategy builder is
  Next.js-native and we want to keep upstream diffs cheap.
