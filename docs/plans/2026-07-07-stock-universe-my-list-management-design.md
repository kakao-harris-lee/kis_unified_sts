# Stock Universe "My List" Management — Design

Date: 2026-07-07
Status: Design (validated via brainstorming, ready for implementation plan)
Topic: Ergonomic management of the stock trading universe, separating operator
picks ("My List") from system-found candidates, and removing the raw-code-entry
friction when adding stocks.

## Problem

The stock trading universe is already a sophisticated, dynamic, multi-source
pipeline (real-time screener over KIS ranking APIs, fusion ranker blending
screener + LLM quality scores + themes, daily pre-market technical scanner, theme
discovery), unioned and capped at `STOCK_MAX_SYMBOLS` (default 40) into an
"effective universe" the trading pipeline consumes. A full management page
already exists at `/universe`.

Despite this, the operator experience is weak in two specific ways:

1. **Management is unergonomic.** Manually adding a stock forces a raw form
   (symbol code, name, reason, TTL-hours). The operator thinks in terms of *two
   universes* — "what the system found" vs. "what I added" — but the UI blends
   the operator's picks into the 40-row system table as small "Pinned" badges.
2. **Adding requires raw codes with no confirmation.** You type a 6-digit code
   with no feedback on whether it resolved to the company you intended.

## Goals

- Elevate operator picks to a first-class **"My List"**, visually separated from
  system-found candidates.
- Make adding a stock frictionless: type a code, see the resolved name for
  confirmation, one-click add. Permanent by default.
- Change **no trading behavior** — this is a presentation + ergonomics change over
  an existing mechanism.

## Non-Goals (YAGNI)

- **No name-based search / autocomplete.** Decision: "codes are fine, just
  validate." Building a full KRX code↔name master (all ~2,500 symbols) requires a
  `KRX_API_KEY` (documented but not set in the live env) plus new fetch/persist/
  search backend work. Out of scope. We resolve names only from what the system
  already knows.
- **No block list.** Decision: trending / live-interest stocks are the priority
  trade targets anyway, so actively maintaining an exclusion list is overhead for
  edge cases. The backend `action=exclude` primitive stays **dormant** (not
  removed — zero cost to leave, churn to rip out); the UI simply offers no block
  action.
- **No bulk add.** One code at a time.
- **No new storage.** Reuses the existing override structure.

## Key Insight

The backend already has the exact primitive needed. `stock:universe:overrides`
(Redis) stores manual actions per symbol with `action ∈ {include, exclude,
remove}`. "My List" is simply **the `include` overrides**, re-presented as a
first-class collection instead of badges in the system table. The effective
universe already unions manual includes in and filters excludes out, so trading
behavior is untouched.

## Data Model

No new storage. Three logical sets over existing data:

- **My List** = overrides where `action = include` → forced into the universe.
- **System-found** = screener / fusion / daily-scanner / theme candidates
  (unchanged).
- **Effective universe** = the existing union-capped snapshot the pipeline
  consumes (unchanged).

Relevant existing code:
- `shared/stock_universe/effective.py` — `build_effective_universe_snapshot()`,
  `_normalize_override_bucket()`, name merge (`extract_names` / `_merge_names`).
  The read layer already treats a **missing `expires_at` as permanent**
  (`_normalize_override_bucket`, ~lines 263–276: an item expires only when
  `expires_at` is set and in the past).
- `services/dashboard/routes/universe.py` — router `prefix="/api/trading/universe"`
  with `GET /`, `GET /sources`, `GET /audit`, `POST /recompute`,
  `POST /overrides`.

## Layout (`/universe`)

Two clearly separated regions, top to bottom:

**Summary stat row (very top).** `My List: N · System: M · Effective total: K /
cap 40` — operator's contribution vs. system's, and headroom to the cap.

**Region A — My List (top, primary).**
- A single **"+ Add stock"** input at the top (the add flow, below).
- Card/table of operator picks: `SymbolLabel` (name + code), resolved-name
  confirmation state, active-in-effective state, added-date, one-click
  **Remove**.
- Always visible, even when empty (empty state: "아직 추가한 종목이 없습니다 —
  위에서 추가하세요").

**Region B — System-found (below, secondary).**
- Today's table minus manual-override noise: rank, symbol, active / market-data
  state, score, daily indicator, contributing sources, reason. Read-only.
- Per-source freshness table (collapsible) and the **Recompute** button live
  here (they concern the system pipeline).

Mental model the layout enforces: **top is mine, bottom is the system's.**

## Add Flow

Inline at the top of My List, replacing the raw form:

1. **Type a code.** Single input, 6-digit KRX code. Client-side: exactly 6
   digits or the Add button is disabled with an inline error.
2. **Confirm the name.** Debounced call to a resolve endpoint returns what the
   system knows:
   - **Known** → `삼성전자 · 005930` with a green check.
   - **Pending** → `005930 · 이름 확인 예정` (name resolves later once a feed
     carries it). Still addable — decision: **add anyway**, no soft warn.
   - **Invalid** → inline error, Add disabled.
3. **Add.** One button. No required reason (optional behind a small "메모 추가"
   link). No TTL field — **permanent by default**. On success the stock appears
   at the top of My List optimistically and the effective universe recomputes.

## Backend Changes

All in `services/dashboard/routes/universe.py` unless noted.

1. **`GET /api/trading/universe/resolve?code=` (new).** Validates 6-digit format;
   looks up the name via the existing name cache
   (`extract_names` / `_merge_names` in `shared/stock_universe/effective.py`);
   returns `{code, name: string|null, known: boolean}`. Pure read, no side
   effects.
2. **`POST /api/trading/universe/overrides` (existing, adjusted).** For
   `action=include` with no `expires_at` / `ttl_seconds`, persist with **no
   expiry (permanent)**. The read/normalization layer already treats missing
   expiry as permanent; the one behavioral check is whether the **write path**
   stamps the Redis key with `DEFAULT_OVERRIDES_TTL_SECONDS` (48h,
   `effective.py:18`). If it does, exempt permanent includes from that key TTL.
   This is the single genuine behavioral fix.
3. **Snapshot origin.** Ensure each snapshot row's origin cleanly distinguishes
   `manual_include` so the frontend splits My List from System-found without
   heuristics. Likely already present via the `sources` field — verify.

## Frontend Changes

- `strategy-builder-ui/src/app/universe/page.tsx` — two-region layout, the
  add-with-resolve input, optimistic insert, remove.
- `strategy-builder-ui/src/lib/dashboard/universe.ts` — add `resolveCode(code)`
  client method for the new resolve endpoint.
- Reuse `SymbolLabel`, `TableSkeleton`, existing React Query
  (`useQueryWithError`) + mutation patterns, `RefreshIndicator`, `ErrorMessage`,
  `HeaderBar`.

## Testing

- **Backend (hermetic + fakeredis pattern):**
  - `resolve` endpoint: known / pending / invalid code.
  - Permanent include persists with no TTL (key survives past 48h boundary or is
    stored without expiry).
  - Snapshot origin split: a manual include is distinguishable from system rows.
- **Frontend:**
  - Add flow states: known → confirm; pending → add anyway; invalid → disabled.
  - Optimistic insert and remove.

## Non-Negotiables Honored

- **Config-driven:** cap remains `STOCK_MAX_SYMBOLS`; no hardcoded thresholds.
- **Redis DB 1 + TTLs:** permanent manual includes are an intentional,
  documented exception for operator picks (they must not silently expire).
- **No trading-behavior change:** effective-universe computation is untouched;
  this is presentation + one write-path TTL fix.
- **DRY:** reuses the existing override primitive and name-merge logic; no
  duplicate universe store.

## Open Implementation Checks

1. Confirm the `POST /overrides` write path's TTL handling (the one behavioral
   fix above).
2. Confirm `manual_include` origin is already exposed per row in the snapshot; if
   not, add it.
3. Confirm the name cache reachable from the route covers "known" resolution
   adequately for typical operator picks (liquid names the system has seen).
