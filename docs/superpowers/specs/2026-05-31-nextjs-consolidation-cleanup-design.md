# Next.js Consolidation Cleanup — Design

**Status**: approved (2026-05-31)
**Owner**: operator
**Driver**: Finish ("마저 정리") the Vite → Next.js migration begun in
`docs/plans/archive/2026-05-28-vite-dashboard-to-nextjs-migration.md`. That migration's
phases 0–5 already shipped (PRs #346, #350, #353, #355, #359–#361): the Vite SPA
`dashboard-frontend/` is deleted, every page runs on Next.js
(`strategy-builder-ui/`), Caddy is the single external entry on `:5080`, and the
container runs a multi-stage `next build` + `next start`. What remains is
residual cleanup, a light client tidy, and an end-to-end verification pass.

## Goal

Eliminate every residual artifact of the now-deleted dual-frontend era, lightly
restructure the STS-native Next.js API client for clarity (no behavior change),
and verify the whole stack end-to-end on `:5080`.

## Background / current state (verified 2026-05-31)

- **One frontend.** `strategy-builder-ui/` (Next.js 16, App Router) serves all
  UI: `/`, `/positions`, `/signals`, `/trades`, `/builder`, `/execute`. No
  `dashboard-frontend/` directory exists anywhere in the repo.
- **FastAPI is API-only.** `services/dashboard/app.py` `/` returns a JSON
  pointer; there is **no `StaticFiles` mount**. Only stale *comments* remain.
- **Caddy** routes STS-native `/api/*` + `/health|/docs|/metrics` to
  `dashboard:8001`; everything else (UI, `/_next/*`, upstream-compat
  `/api/{auth,account,orders,market,symbols,files}`) to
  `strategy-builder-ui:3100`.
- **Two API clients split cleanly along the upstream/STS boundary** — confirmed
  no cross-imports:
  - `src/lib/api/` — **upstream KIS** client (fetch-based). Used by
    `/builder` and `/execute`. Tracked verbatim from
    `koreainvestment/open-trading-api` per `UPSTREAM.md`.
  - `src/lib/dashboard/api.ts` — **STS-native** client (axios, 112 lines, 9 API
    groups). Used by Cockpit/positions/signals/trades.
- `src/types/` is upstream-tracked; `src/lib/dashboard/types.ts` is STS types.

## Non-goals (explicit — prevent scope creep)

- **No** merging `src/lib/api/` (upstream) with `src/lib/dashboard/api.ts`
  (STS). They are separate by design; merging fights upstream and makes future
  `open-trading-api` pulls painful (`UPSTREAM.md`: "Keep upstream UI changes
  minimal").
- **No** touching `src/types/` (upstream-tracked).
- **No** auth model / HTTPS / mobile-app / page-restyle work (theme already
  unified in #355).
- **No** changes to Caddy routing behavior (only stale comments, if any).

## Workstreams

### WS1 — Backend dead-code & comment cleanup (`services/dashboard/`)

1. Fix stale module docstring `app.py:4` — currently "The React app is built
   from dashboard-frontend/ and served as static files." → describe the
   API-only reality (UI served by `strategy-builder-ui` via Caddy).
2. Fix `_register_routes` docstring (`app.py:190`) — "Register API routes and
   React SPA static file serving." → drop the SPA clause.
3. Grep-confirm no `StaticFiles`, SPA mount, or `dashboard-frontend` path
   reference remains in `services/dashboard/`.
4. **`HTMLViewMiddleware` — KEEP (approved).** It renders JSON→HTML when a
   browser (`Accept: text/html`) hits `/api/*` directly; still reachable via
   Caddy (`:5080/api/trading/status` in a browser) and gives operators a debug
   view, so it is **not dead**. Action: keep the middleware as-is; only update
   any stale surrounding comment. Do **not** remove.

### WS2 — Repo-wide stale-reference sweep

Update live references to the deleted `dashboard-frontend/`:

- `AGENTS.md`, `unified_trading_architecture.md` — update prose to the
  Next.js-only reality.
- `docker-compose.yml` caddy comment (~line 160): "Everything else →
  dashboard:8001 (Vite SPA + FastAPI)" → "Next.js + FastAPI".
- `caddy/Caddyfile` — re-verify comments are current (header dated 2026-05-29;
  fix any lingering Vite mention).
- Source comments in `src/lib/dashboard/types.ts`,
  `src/hooks/dashboard/useLocalStorage.ts`,
  `src/contexts/dashboard/AssetClassContext.tsx` — fix misleading comments.
  **Keep** any `dashboard-frontend`-named **localStorage key** verbatim
  (renaming silently resets operator preferences); only the comment changes.
- Mark `docs/plans/archive/2026-05-28-vite-dashboard-to-nextjs-migration.md` status as
  ✅ DONE with a one-line completion note pointing at this spec.
- **Leave `docs/plans/archive/*` untouched** (historical record).

Each file is audited individually; a reference is only changed when it is
factually stale, never mechanically.

### WS3 — STS-native client structural tidy (no behavior change)

Split `src/lib/dashboard/api.ts` (112 lines, 9 groups: trading, signals,
trades, strategies, strategyLab, strategyBuilder, fills, health, killSwitch)
into per-domain modules matching the `src/lib/api/` house style:

- Extract the shared axios instance into `src/lib/dashboard/client.ts`.
- One file per domain (e.g. `trading.ts`, `signals.ts`, `trades.ts`, …) each
  importing the shared client.
- **Keep `api.ts` as a thin re-export barrel** so every existing import
  (`from '@/lib/dashboard/api'`) keeps working unchanged — zero call-site edits.
- `lib/dashboard/types.ts` stays the STS types home (no merge with upstream
  `src/types/`).

Gate: `npx tsc --noEmit` + `npm run build` + `npm run lint` (eslint) in
`strategy-builder-ui/` must all pass with no new errors.

### WS4 — End-to-end verification ("끝까지 검증")

1. `docker compose build dashboard strategy-builder-ui`.
2. `docker compose up -d redis dashboard strategy-builder-ui caddy`.
3. Smoke test through Caddy on `:5080`:
   - `GET /` → Next.js Cockpit, HTTP 200, no Next error overlay.
   - `GET /positions`, `/signals`, `/trades`, `/builder`, `/execute` → 200.
   - `GET /api/health`, `/api/trading/status`, `/api/signals`, `/api/trades`
     → reachable (200 JSON or graceful-empty).
   - `GET /api/kis-builder/<presets>` → reachable (upstream-compat path).
   - WebSocket `/ws` connects.
   - Browser console: zero uncaught errors per page (headless check).
4. `docker compose down` after verification.

**Honest coverage note.** ClickHouse (`host.docker.internal:9000`), Redis auth,
and KIS credentials may be unavailable in the verification environment. When
that happens, data endpoints return handled/empty responses. The pass bar is
**"pages render, routing is correct, no regression versus `main`"** — not "live
trading data." The implementation report will state exactly which checks ran
with real data and which were structural-only.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Splitting `api.ts` breaks imports | Thin re-export barrel + `tsc`/`build`/`lint` gate before commit. |
| Editing an upstream file by mistake | WS3 touches only `src/lib/dashboard/**`; `src/lib/api/**` and `src/types/**` are off-limits. |
| Renaming a localStorage key resets operator prefs | Keep keys verbatim; change comments only. |
| Verification env lacks ClickHouse/KIS | Partial smoke test; coverage explicitly reported. |
| Mechanical doc edits introduce inaccuracy | Audit each reference individually; change only when factually stale. |

## Acceptance criteria

- [ ] No `services/dashboard/` comment/docstring references a static SPA or
      `dashboard-frontend/`.
- [ ] No live (non-archive) doc or compose/Caddy comment references the deleted
      Vite SPA as current.
- [ ] `HTMLViewMiddleware` retained; surrounding comments accurate.
- [ ] `src/lib/dashboard/api.ts` split into `client.ts` + per-domain files with
      a re-export barrel; **all existing imports unchanged**.
- [ ] `tsc --noEmit`, `npm run build`, `npm run lint` pass in
      `strategy-builder-ui/`.
- [ ] `pytest tests/` (dashboard-relevant suites) pass via `.venv`.
- [ ] Stack boots on `:5080`; all six pages render and routing is correct;
      verification coverage documented honestly.
- [ ] Migration plan doc marked DONE.

## Out of scope

- API-client merge (upstream + STS). Forbidden by design.
- HTTPS termination, auth hardening, mobile app (inherited from the 2026-05-28
  plan's out-of-scope list).
