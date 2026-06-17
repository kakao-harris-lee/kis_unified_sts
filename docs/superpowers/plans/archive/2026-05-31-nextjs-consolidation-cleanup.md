# Next.js Consolidation Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every residual artifact of the deleted Vite+Next.js dual-frontend era, split the STS-native Next.js API client into per-domain modules behind a re-export barrel, and verify the whole stack end-to-end on `:5080`.

**Architecture:** This is a cleanup + refactor, not a feature. The "tests" are the TypeScript compiler, the Next.js production build, eslint, the Python test suite, and an end-to-end smoke test through Caddy. The client split is behavior-preserving: a thin re-export barrel (`api.ts`) keeps all 12 existing import sites (`@/lib/dashboard/api`) working unchanged.

**Tech Stack:** Next.js 16 (App Router), TypeScript, axios, FastAPI, Docker Compose, Caddy.

**Spec:** `docs/superpowers/specs/2026-05-31-nextjs-consolidation-cleanup-design.md`

**Branch:** `chore/nextjs-consolidation-cleanup` (already created; spec committed at `6851b52`).

**Hard constraints (do NOT violate):**
- Do **not** edit `strategy-builder-ui/src/lib/api/**` (upstream KIS, fetch-based).
- Do **not** edit `strategy-builder-ui/src/types/**` (upstream-tracked).
- Do **not** merge the upstream and STS clients.
- Do **not** remove `HTMLViewMiddleware` (operator debug view; keep it).
- Do **not** touch `docs/plans/archive/**`.

---

## File Map

**WS1 — backend comment cleanup**
- Modify: `services/dashboard/app.py` (module docstring lines 1-5; `_register_routes` docstring line 190)

**WS2 — stale-reference sweep**
- Modify: `AGENTS.md` (lines 13, 33)
- Modify: `unified_trading_architecture.md` (line 44)
- Modify: `docker-compose.yml` (caddy comment ~line 160)
- Audit only: `caddy/Caddyfile`; `strategy-builder-ui/src/lib/dashboard/types.ts:1`; `strategy-builder-ui/src/hooks/dashboard/useLocalStorage.ts:1`; `strategy-builder-ui/src/contexts/dashboard/AssetClassContext.tsx:3`
- Modify: `docs/plans/archive/2026-05-28-vite-dashboard-to-nextjs-migration.md` (status → DONE)

**WS3 — STS-native client split** (all under `strategy-builder-ui/src/lib/dashboard/`)
- Create: `client.ts`, `trading.ts`, `signals.ts`, `trades.ts`, `strategies.ts`, `strategyLab.ts`, `strategyBuilder.ts`, `fills.ts`, `health.ts`, `killSwitch.ts`
- Modify (rewrite as barrel): `api.ts`

**WS4 — end-to-end verification**
- No source changes. Produces a verification note appended to this plan's PR description / commit.

---

## Task 1: Backend comment cleanup (WS1)

**Files:**
- Modify: `services/dashboard/app.py`

Docstring-only edits. They cannot change runtime behavior; the verification is that the module still imports and dashboard tests still pass.

- [ ] **Step 1: Fix the module docstring**

In `services/dashboard/app.py`, replace lines 1-5:

```python
"""FastAPI dashboard application.

Serves the React SPA frontend and provides API endpoints for trading data.
The React app is built from dashboard-frontend/ and served as static files.
"""
```

with:

```python
"""FastAPI dashboard application.

API-only service: provides trading-data endpoints under /api/* plus /health,
/docs, /metrics, and the /ws WebSocket. The UI is served separately by the
Next.js app (strategy-builder-ui) and reaches these endpoints through Caddy on
:5080. (The Vite SPA that used to be served from here was removed in the
Next.js consolidation — see docs/plans/archive/2026-05-28-vite-dashboard-to-nextjs-migration.md.)
"""
```

- [ ] **Step 2: Fix the `_register_routes` docstring**

In `services/dashboard/app.py`, find:

```python
def _register_routes(app: FastAPI) -> None:
    """Register API routes and React SPA static file serving."""
```

replace the docstring line with:

```python
def _register_routes(app: FastAPI) -> None:
    """Register API routers, the /ws WebSocket, and the root pointer endpoint."""
```

- [ ] **Step 3: Confirm no static-SPA debris remains in the dashboard service**

Run:

```bash
cd /home/deploy/project/kis_unified_sts
grep -rIn "StaticFiles\|dashboard-frontend\|React SPA\|static file" services/dashboard/
```

Expected: **no matches** (the two docstrings above are now fixed; `HTMLViewMiddleware` is unrelated and stays). If any other match appears, inspect it — it is either another stale comment to fix or a real mount that contradicts the spec (stop and report).

- [ ] **Step 4: Verify the module still imports**

Run:

```bash
cd /home/deploy/project/kis_unified_sts
.venv/bin/python -c "from services.dashboard.app import create_app; create_app(); print('OK')"
```

Expected: prints `OK` (no import/syntax error). If `create_app()` requires env/Redis and raises, fall back to import-only: `.venv/bin/python -c "import services.dashboard.app; print('OK')"`.

- [ ] **Step 5: Run the dashboard Python tests**

Run:

```bash
cd /home/deploy/project/kis_unified_sts
.venv/bin/pytest tests/services/ -q
```

Expected: PASS (same result as on `main`; docstring edits change nothing). If `tests/services/` does not exist, run `.venv/bin/pytest tests/ -q -k dashboard`.

- [ ] **Step 6: Commit**

```bash
cd /home/deploy/project/kis_unified_sts
git add services/dashboard/app.py
git commit -m "docs(dashboard): drop stale Vite-SPA references in app.py docstrings

FastAPI is API-only after the Next.js consolidation; the module no longer
serves a static SPA. HTMLViewMiddleware retained (operator debug view)."
```

---

## Task 2: Stale-reference sweep (WS2)

**Files:**
- Modify: `AGENTS.md`, `unified_trading_architecture.md`, `docker-compose.yml`, `docs/plans/archive/2026-05-28-vite-dashboard-to-nextjs-migration.md`
- Audit only: `caddy/Caddyfile`, three source provenance comments

- [ ] **Step 1: Fix `AGENTS.md`**

Line 13 currently:

```markdown
- `dashboard-frontend/`: React + Vite UI.
```

replace with:

```markdown
- `strategy-builder-ui/`: Next.js (App Router) UI — the single frontend. Serves the dashboard (Cockpit/positions/signals/trades) and the strategy builder/executor.
```

Line 33 currently:

```markdown
- Frontend: `cd dashboard-frontend && npm run dev|build|lint`.
```

replace with:

```markdown
- Frontend: `cd strategy-builder-ui && npm run dev|build|lint`.
```

- [ ] **Step 2: Fix `unified_trading_architecture.md`**

Line 44 currently:

```
├── dashboard-frontend/        # React 프론트엔드
```

replace with:

```
├── strategy-builder-ui/       # Next.js 프론트엔드 (단일 앱)
```

- [ ] **Step 3: Fix the Caddy comment in `docker-compose.yml`**

Find the comment block above the `caddy:` service (around line 158-161). The stale line reads:

```yaml
  # Everything else → dashboard:8001 (Vite SPA + FastAPI).
```

replace with:

```yaml
  # Everything else → strategy-builder-ui:3100 (Next.js UI + /_next assets).
```

Also re-read the two lines above it; if they still describe routing as if the Vite SPA exists, align them with the actual Caddyfile (UI/`_next`/catch-all → Next.js; STS `/api/*` + `/health|/docs|/metrics` → dashboard). Keep edits to comments only — do not change any compose `services:` config.

- [ ] **Step 4: Audit `caddy/Caddyfile` (likely no change)**

Run:

```bash
cd /home/deploy/project/kis_unified_sts
grep -n "Vite\|dashboard-frontend\|SPA" caddy/Caddyfile
```

Expected: no matches (header is dated 2026-05-29 and already describes the Next.js catch-all). If a stale mention appears, fix the comment to match the actual routing; otherwise leave the file untouched.

- [ ] **Step 5: Audit the three source provenance comments (keep as-is)**

Run:

```bash
cd /home/deploy/project/kis_unified_sts
grep -n "dashboard-frontend" \
  strategy-builder-ui/src/lib/dashboard/types.ts \
  strategy-builder-ui/src/hooks/dashboard/useLocalStorage.ts \
  strategy-builder-ui/src/contexts/dashboard/AssetClassContext.tsx
```

Expected matches are **provenance comments** (e.g. `// Ported from dashboard-frontend/src/contexts/AssetClassContext.tsx`). These are accurate history, not misleading architecture claims, and there are no `dashboard-frontend`-named localStorage keys. **Decision: leave them unchanged.** No edit in this step — it is a confirmation gate. (If any line instead asserts the file is *currently served by* dashboard-frontend, fix that specific wording.)

- [ ] **Step 6: Mark the 2026-05-28 migration plan DONE**

In `docs/plans/archive/2026-05-28-vite-dashboard-to-nextjs-migration.md`, change the status header (line 3):

```markdown
**Status**: draft (2026-05-28)
```

to:

```markdown
**Status**: ✅ DONE (2026-05-31) — phases 0–5 shipped (PRs #346, #350, #353, #355, #359–#361). Residual cleanup tracked in docs/superpowers/specs/2026-05-31-nextjs-consolidation-cleanup-design.md.
```

- [ ] **Step 7: Confirm no live (non-archive) stale references remain**

Run:

```bash
cd /home/deploy/project/kis_unified_sts
grep -rIn "dashboard-frontend" \
  --include=*.md --include=*.yml --include=*.yaml --include=*.py \
  --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.next \
  . | grep -v "docs/plans/archive/" | grep -v "docs/superpowers/specs/2026-05-31" | grep -v "docs/plans/archive/2026-05-28-vite-dashboard-to-nextjs-migration.md"
```

Expected: the only remaining matches are the three TS provenance comments from Step 5 (intentionally kept). Anything else is a miss — fix it.

- [ ] **Step 8: Commit**

```bash
cd /home/deploy/project/kis_unified_sts
git add AGENTS.md unified_trading_architecture.md docker-compose.yml docs/plans/archive/2026-05-28-vite-dashboard-to-nextjs-migration.md
git commit -m "docs: sweep stale dashboard-frontend (Vite SPA) references

Update AGENTS.md, architecture doc, and the Caddy compose comment to the
Next.js-only reality; mark the 2026-05-28 migration plan DONE. TS provenance
comments intentionally retained as accurate history."
```

---

## Task 3: Split the STS-native API client (WS3)

**Files:**
- Create: `strategy-builder-ui/src/lib/dashboard/client.ts` and 9 per-domain files
- Modify (rewrite as barrel): `strategy-builder-ui/src/lib/dashboard/api.ts`

Behavior-preserving refactor. The barrel re-exports every symbol so all 12 call sites importing `@/lib/dashboard/api` keep working. Verified by `tsc`, `build`, and `lint`.

- [ ] **Step 1: Create the shared axios client**

Create `strategy-builder-ui/src/lib/dashboard/client.ts`:

```ts
import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add API key header if configured
const apiKey = process.env.NEXT_PUBLIC_API_KEY;
if (apiKey) {
  apiClient.defaults.headers.common['X-API-Key'] = apiKey;
}
```

- [ ] **Step 2: Create `trading.ts`**

Create `strategy-builder-ui/src/lib/dashboard/trading.ts`:

```ts
import { apiClient } from './client';

// Trading API
export const tradingApi = {
  getStatus: (params?: { asset_class?: string }) =>
    apiClient.get('/api/trading/status', { params }),
  getPositions: (params?: { asset_class?: string }) =>
    apiClient.get('/api/trading/positions', { params }),
  startTrading: (params?: { asset_class?: string }) =>
    apiClient.post('/api/trading/start', null, { params }),
  stopTrading: (params?: { asset_class?: string }) =>
    apiClient.post('/api/trading/stop', null, { params }),
};
```

- [ ] **Step 3: Create `signals.ts`**

Create `strategy-builder-ui/src/lib/dashboard/signals.ts`:

```ts
import { apiClient } from './client';

// Signals API
export const signalsApi = {
  getSignals: (params?: { asset_class?: string; strategy?: string; side?: string; limit?: number }) =>
    apiClient.get('/api/signals', { params }),
  getHistory: (params?: { asset_class?: string; days?: number }) =>
    apiClient.get('/api/signals/history', { params }),
};
```

- [ ] **Step 4: Create `trades.ts`**

Create `strategy-builder-ui/src/lib/dashboard/trades.ts`:

```ts
import { apiClient } from './client';

// Trades API
export const tradesApi = {
  getTrades: (params?: { strategy?: string; side?: string; limit?: number }) =>
    apiClient.get('/api/trades', { params }),
  getStatistics: () => apiClient.get('/api/trades/statistics'),
  getByStrategy: () => apiClient.get('/api/trades/by-strategy'),
  // ClickHouse RL endpoints
  getRlStatistics: (params?: { asset_class?: string; strategy?: string }) =>
    apiClient.get('/api/trades/rl/statistics', { params }),
  getRlTrades: (params?: { asset_class?: string; strategy?: string; limit?: number }) =>
    apiClient.get('/api/trades/rl', { params }),
};
```

- [ ] **Step 5: Create `strategies.ts`**

Create `strategy-builder-ui/src/lib/dashboard/strategies.ts`:

```ts
import { apiClient } from './client';

// Strategies API
export const strategiesApi = {
  list: (params?: { asset_class?: string; enabled_only?: boolean }) =>
    apiClient.get('/api/strategies', { params }),
};
```

- [ ] **Step 6: Create `strategyLab.ts`**

Create `strategy-builder-ui/src/lib/dashboard/strategyLab.ts`:

```ts
import { apiClient } from './client';

// Strategy Lab API
export const strategyLabApi = {
  getCapabilities: () => apiClient.get('/api/strategy-lab/capabilities'),
  validate: (spec: unknown) => apiClient.post('/api/strategy-lab/validate', spec),
  previewCode: (spec: unknown) => apiClient.post('/api/strategy-lab/preview-code', spec),
  previewSignal: (payload: unknown) =>
    apiClient.post('/api/strategy-lab/preview-signal', payload),
  getSignal: (signalId: string) =>
    apiClient.get(`/api/strategy-lab/signals/${signalId}`),
  createOrderTicket: (
    signalId: string,
    payload?: { quantity?: number; order_amount?: number },
  ) => apiClient.post(`/api/strategy-lab/signals/${signalId}/order-ticket`, payload || {}),
  submitPaperOrder: (ticketId: string) =>
    apiClient.post('/api/strategy-lab/orders/paper', { ticket_id: ticketId }),
};
```

- [ ] **Step 7: Create `strategyBuilder.ts`**

Create `strategy-builder-ui/src/lib/dashboard/strategyBuilder.ts`:

```ts
import { apiClient } from './client';

// Strategy Builder API
export const strategyBuilderApi = {
  getCapabilities: () => apiClient.get('/api/strategy-builder/capabilities'),
  validate: (state: unknown) => apiClient.post('/api/strategy-builder/validate', state),
  previewYaml: (state: unknown) => apiClient.post('/api/strategy-builder/preview-yaml', state),
  previewCode: (state: unknown) => apiClient.post('/api/strategy-builder/preview-code', state),
  importYaml: (yaml: string) => apiClient.post('/api/strategy-builder/import-yaml', { yaml }),
  previewSignals: (payload: unknown) =>
    apiClient.post('/api/strategy-builder/signals/preview', payload),
  createOrderTicket: (
    signalId: string,
    payload?: { quantity?: number; order_amount?: number },
  ) => apiClient.post(`/api/strategy-builder/signals/${signalId}/order-ticket`, payload || {}),
  submitPaperOrder: (ticketId: string) =>
    apiClient.post('/api/strategy-builder/orders/paper', { ticket_id: ticketId }),
};
```

- [ ] **Step 8: Create `fills.ts`**

Create `strategy-builder-ui/src/lib/dashboard/fills.ts`:

```ts
import { apiClient } from './client';

// Fills API (Phase 2)
export const fillsApi = {
  getRecent: (params?: { asset_class?: string; limit?: number }) =>
    apiClient.get('/api/trades/fills', { params }),
};
```

- [ ] **Step 9: Create `health.ts`**

Create `strategy-builder-ui/src/lib/dashboard/health.ts`:

```ts
import { apiClient } from './client';

// Health API (Phase 1 backend)
export const healthApi = {
  getSummary: (params?: { asset_class?: string }) =>
    apiClient.get('/api/health/summary', { params }),
  getProcess: () => apiClient.get('/api/health/process'),
  getDataFreshness: (params?: { asset_class?: string }) =>
    apiClient.get('/api/health/data-freshness', { params }),
  getKillSwitch: () => apiClient.get('/api/health/kill-switch'),
};
```

- [ ] **Step 10: Create `killSwitch.ts`**

Create `strategy-builder-ui/src/lib/dashboard/killSwitch.ts`:

```ts
import { apiClient } from './client';

// Kill Switch API (Phase 2)
export const killSwitchApi = {
  trigger: () => apiClient.post('/api/trading/kill-switch'),
};
```

- [ ] **Step 11: Rewrite `api.ts` as a re-export barrel**

Replace the **entire** contents of `strategy-builder-ui/src/lib/dashboard/api.ts` with:

```ts
// STS-native dashboard API client.
//
// Split into per-domain modules (./client + ./<domain>). This file is a thin
// re-export barrel so existing import paths (`@/lib/dashboard/api`) keep working
// for every call site. This client is SEPARATE from the upstream KIS client in
// src/lib/api/ by design — do not merge them (see strategy-builder-ui/UPSTREAM.md).
export { apiClient } from './client';
export { tradingApi } from './trading';
export { signalsApi } from './signals';
export { tradesApi } from './trades';
export { strategiesApi } from './strategies';
export { strategyLabApi } from './strategyLab';
export { strategyBuilderApi } from './strategyBuilder';
export { fillsApi } from './fills';
export { healthApi } from './health';
export { killSwitchApi } from './killSwitch';
```

- [ ] **Step 12: Type-check (this is the regression test for the split)**

Run:

```bash
cd /home/deploy/project/kis_unified_sts/strategy-builder-ui
npx tsc --noEmit
```

Expected: no errors. A missing/renamed export here means a call site broke — fix the barrel (the exported names must exactly match: `apiClient`, `tradingApi`, `signalsApi`, `tradesApi`, `strategiesApi`, `strategyLabApi`, `strategyBuilderApi`, `fillsApi`, `healthApi`, `killSwitchApi`).

- [ ] **Step 13: Lint**

Run:

```bash
cd /home/deploy/project/kis_unified_sts/strategy-builder-ui
npm run lint
```

Expected: no new errors versus `main`.

- [ ] **Step 14: Production build**

Run:

```bash
cd /home/deploy/project/kis_unified_sts/strategy-builder-ui
npm run build
```

Expected: build succeeds (all pages compile). This proves every consumer of `@/lib/dashboard/api` still resolves.

- [ ] **Step 15: Commit**

```bash
cd /home/deploy/project/kis_unified_sts
git add strategy-builder-ui/src/lib/dashboard/
git commit -m "refactor(ui): split STS-native dashboard API client into per-domain modules

Extract the axios instance to client.ts and one file per API group; api.ts
becomes a thin re-export barrel so all 12 call sites are untouched. Kept
separate from the upstream KIS client (src/lib/api) by design. No behavior
change — verified by tsc --noEmit, eslint, and next build."
```

---

## Task 4: End-to-end verification (WS4)

**Files:** none (verification + report).

No source changes. Boot the stack through Caddy and smoke-test. Document coverage honestly — data endpoints may return empty if ClickHouse/Redis/KIS are unavailable in this environment; the bar is "pages render, routing correct, no regression."

- [ ] **Step 1: Build the two app images**

Run:

```bash
cd /home/deploy/project/kis_unified_sts
docker compose build dashboard strategy-builder-ui
```

Expected: both images build (the Next.js image runs the multi-stage `next build`). If the build fails, stop — Task 3 introduced a break.

- [ ] **Step 2: Start the minimal stack**

Run:

```bash
cd /home/deploy/project/kis_unified_sts
docker compose up -d redis dashboard strategy-builder-ui caddy
sleep 20
docker compose ps
```

Expected: `redis`, `dashboard`, `strategy-builder-ui`, `caddy` all `Up` (dashboard/builder-ui report `healthy` after the start period). If a container is unhealthy, capture `docker compose logs <svc> --tail=50` into the report.

- [ ] **Step 3: Smoke-test the six UI pages through Caddy**

Run:

```bash
for p in / /positions /signals /trades /builder /execute; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5080$p")
  echo "$p -> $code"
done
```

Expected: every path returns `200`. Record the actual codes in the report. (A `200` from Caddy on these paths confirms routing to Next.js and that the page rendered server-side without a fatal error.)

- [ ] **Step 4: Smoke-test the API + upstream-compat routes through Caddy**

Run:

```bash
for p in /api/health /api/trading/status /api/signals /api/trades /api/kis-builder/presets; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5080$p")
  echo "$p -> $code"
done
```

Expected: each route is **reachable** — `200` (data or graceful-empty). A `404` on `/api/kis-builder/presets` means the exact preset path differs; confirm the real path from `services/dashboard/routes/kis_builder.py` and re-test. `5xx` from a data route is acceptable **only** if it is a handled "backend unavailable" (ClickHouse/Redis down in this env) — note which, and distinguish from a routing failure.

- [ ] **Step 5: Verify the WebSocket endpoint upgrades**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  "http://localhost:5080/ws"
```

Expected: `101` (switching protocols) or `426`/`400` from the server's WS handshake validation — any of these proves the `/ws` route reaches the backend. A `404`/`502` means routing is broken (report it).

- [ ] **Step 6: Check the browser console for uncaught errors**

Use the Chrome DevTools MCP (`mcp__plugin_chrome-devtools-mcp_chrome-devtools__*`) or Playwright MCP:

1. `navigate_page` to `http://localhost:5080/`, then to `/positions`, `/signals`, `/trades`, `/builder`, `/execute`.
2. After each, call `list_console_messages` and record any `error`-level messages.

Expected: zero uncaught/error-level console messages attributable to app code (ignore benign network errors from absent ClickHouse/KIS data — note them separately). If the MCP browser is unavailable, state that in the report and rely on Steps 3-5 (HTTP-level) as the coverage ceiling.

- [ ] **Step 7: Tear down**

Run:

```bash
cd /home/deploy/project/kis_unified_sts
docker compose down
```

Expected: containers stopped and removed.

- [ ] **Step 8: Write the verification report**

Create a short results section (for the PR body) capturing, for each check in Steps 3-6: the command, the observed result, and PASS / PASS(structural-only) / FAIL. Explicitly list which checks ran against real data and which were structural-only due to missing ClickHouse/Redis/KIS. No commit needed (this goes in the PR description in Task 5).

---

## Task 5: Open the PR

- [ ] **Step 1: Push the branch**

```bash
cd /home/deploy/project/kis_unified_sts
git push -u origin chore/nextjs-consolidation-cleanup
```

- [ ] **Step 2: Create the PR**

```bash
cd /home/deploy/project/kis_unified_sts
gh pr create --base main --head chore/nextjs-consolidation-cleanup \
  --title "chore(ui): finish Next.js consolidation cleanup" \
  --body "$(cat <<'EOF'
## What
Finish the Vite -> Next.js migration leftovers (spec:
docs/superpowers/specs/2026-05-31-nextjs-consolidation-cleanup-design.md):

- WS1: drop stale Vite-SPA references in dashboard FastAPI docstrings
  (HTMLViewMiddleware retained).
- WS2: sweep stale `dashboard-frontend` references in AGENTS.md, the
  architecture doc, and the Caddy compose comment; mark the 2026-05-28
  migration plan DONE.
- WS3: split the STS-native dashboard API client into per-domain modules
  behind a re-export barrel (no call-site changes; upstream client untouched).

## Why
One clean Next.js codebase with no dual-frontend debris; future upstream
KIS pulls stay cheap (upstream client/types deliberately left separate).

## How tested
- `tsc --noEmit`, `npm run lint`, `npm run build` (strategy-builder-ui) — pass.
- `.venv/bin/pytest tests/services/` — pass.
- End-to-end smoke on :5080 (docker compose): all six pages + API/WS routes.
  <paste the Task 4 verification report here, including structural-only notes>

## Acceptance criteria
See spec. All boxes verified.
EOF
)"
```

- [ ] **Step 3: Run code review**

Invoke the project code-review skill (`/code-review` or `/code-review:code-review`) on the PR and address findings on the same branch.

---

## Self-Review (completed during planning)

**Spec coverage:**
- WS1 (backend dead-code/comments) → Task 1. ✅
- WS2 (stale-reference sweep) → Task 2. ✅
- WS3 (client split) → Task 3. ✅
- WS4 (e2e verification) → Task 4. ✅
- Acceptance criteria (tsc/build/lint/pytest/stack-boot/plan-DONE) → Tasks 1,3,4; migration-plan-DONE in Task 2 Step 6. ✅
- Non-goals respected: hard-constraints block at top forbid touching `src/lib/api`, `src/types`, merging clients, removing `HTMLViewMiddleware`, editing archives. ✅

**Placeholder scan:** No TBD/TODO; every code step shows full file contents; every verification step shows the exact command and expected result.

**Type/name consistency:** Barrel exports in Task 3 Step 11 exactly match the symbols defined in Steps 1-10 and the names consumed by the 12 import sites (`tradingApi`, `signalsApi`, `tradesApi`, `strategiesApi`, `strategyLabApi`, `strategyBuilderApi`, `fillsApi`, `healthApi`, `killSwitchApi`, `apiClient`).
