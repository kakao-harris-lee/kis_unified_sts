# Stock Universe "My List" Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the `/universe` page separate operator picks ("My List") from
system-found candidates, and replace the raw code+name+reason+TTL add form with a
frictionless "type a code → confirm the resolved name → one-click add, permanent
by default" flow.

**Architecture:** Pure presentation + ergonomics change over the existing manual
`include` override primitive. The effective-universe computation and trading
behavior are untouched. Backend adds one read endpoint (`resolve`) and relaxes the
include override to support permanent, reason-optional picks. Frontend restructures
one page into two regions and adds a resolve-on-type add box.

**Tech Stack:** FastAPI + Pydantic (backend, `services/dashboard`), Redis via
`shared.stock_universe`, pytest (fake-fastapi + fake-redis harness). Next.js App
Router + React Query + TypeScript + Tailwind + vitest (frontend,
`strategy-builder-ui`).

**Design doc:** `docs/plans/2026-07-07-stock-universe-my-list-management-design.md`

---

## Context the implementer must know

**The override primitive already exists.** `POST /api/trading/universe/overrides`
with `action=include` forces a symbol into the universe; `remove` deletes the
override. "My List" = the set of `manual_include` overrides. We are re-presenting
existing data, not adding storage.

**Three backend facts that block "permanent, reason-optional":** in
`services/dashboard/routes/universe.py`:
1. `_override_expiry()` (lines 250–257) always returns a timestamp — it defaults to
   a 24h TTL when neither `expires_at` nor `ttl_seconds` is given. So includes can
   never be permanent today.
2. The overrides Redis key is written with a 48h TTL (`_ttl()["overrides"]`, line
   391) — even a null `expires_at` on the item would be lost when the whole key
   expires.
3. `update_trading_universe_override()` **requires a non-empty reason** for
   `include`/`exclude` (lines 342–346).

**Name resolution scope.** `extract_names()`
(`shared/stock_universe/effective.py:113`) pulls code→name from a single payload.
The snapshot's `rows` only cover the capped ~40 already in the universe — but a
stock being *added* is by definition not there yet. So `resolve` must build a
name map from ALL raw source payloads (screener, trade_targets, daily_watchlist,
daily_indicators, theme_targets) plus open positions — the same inputs
`_build_snapshot()` reads.

**Test harness (backend).** `tests/unit/dashboard/test_universe.py` injects a fake
`fastapi` module, reloads the route module, and calls the async route functions
directly (no HTTP). Use the existing `_client(monkeypatch, payloads)` helper and
`_FakeRedis`. Follow its exact shape.

**Test harness (frontend).** vitest (`npm run test` = `vitest run` in
`strategy-builder-ui`). Page/component tests exist, e.g.
`src/app/evidence/page.test.tsx`. React Query is used via `useQueryWithError`.

**Scope guardrails (from design):** no name search, no block-list UI (the
`exclude` action stays in the backend but the UI offers no block button), no bulk
add. Config-driven: cap stays `STOCK_MAX_SYMBOLS`. Permanent manual includes are
an intentional documented exception to the Redis-TTL rule.

**Working branch:** `worktree-stock-universe-my-list` (already checked out in the
worktree). Commit after every task.

---

## Task 1: Backend — permanent, reason-optional include override

**Files:**
- Modify: `services/dashboard/routes/universe.py` (lines 250–257 `_override_expiry`,
  342–346 reason gate, 362–369 include branch, 391 overrides key TTL)
- Test: `tests/unit/dashboard/test_universe.py`

**Step 1: Write the failing tests**

Add to `tests/unit/dashboard/test_universe.py`:

```python
@pytest.mark.asyncio
async def test_include_override_is_permanent_by_default(monkeypatch):
    universe, fake = _client(
        monkeypatch,
        {
            "system:trade_targets:latest": {
                "codes": ["005930"],
                "names": {"005930": "삼성전자"},
            },
        },
    )

    body = await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(
            action="include",
            symbol="000660",
            name="SK하이닉스",
        )
    )

    assert "000660" in body["codes"]
    overrides = json.loads(fake.payloads["stock:universe:overrides"])
    entry = overrides["manual_include"]["000660"]
    # Permanent: no expiry stamped.
    assert entry.get("expires_at") is None
    # Overrides key must not silently expire permanent picks.
    assert "stock:universe:overrides" not in fake.expirations


@pytest.mark.asyncio
async def test_include_override_honors_explicit_ttl(monkeypatch):
    universe, fake = _client(monkeypatch, {})

    await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(
            action="include",
            symbol="000660",
            ttl_seconds=3600,
        )
    )

    overrides = json.loads(fake.payloads["stock:universe:overrides"])
    entry = overrides["manual_include"]["000660"]
    assert entry.get("expires_at") is not None  # explicit TTL still respected
    # Key TTL should cover the requested horizon (not truncate it).
    assert fake.expirations["stock:universe:overrides"] >= 3600


@pytest.mark.asyncio
async def test_include_override_allows_missing_reason(monkeypatch):
    universe, fake = _client(monkeypatch, {})

    body = await universe.update_trading_universe_override(
        universe.UniverseOverrideRequest(action="include", symbol="000660")
    )

    assert "000660" in body["codes"]  # no reason_required error
```

Also confirm the existing `test_universe_override_publishes_snapshot_and_audit`
(exclude + explicit `ttl_seconds=3600`) still passes unchanged — do not break the
exclude path.

**Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/dashboard/test_universe.py -v`
Expected: the 3 new tests FAIL (permanent test fails because `_override_expiry`
stamps 24h and the key gets a 48h TTL; reason test fails with
`HTTPException 400 reason_required`).

**Step 3: Implement**

In `services/dashboard/routes/universe.py`:

(a) Make expiry optional — return `None` when neither field is set:

```python
def _override_expiry(
    request: UniverseOverrideRequest, now: datetime
) -> str | None:
    """Return an ISO expiry, or None for a permanent override.

    Permanent (None) applies when the operator supplies neither an explicit
    ``expires_at`` nor a ``ttl_seconds``. Operator "My List" picks are meant to
    persist until explicitly removed.
    """
    if request.expires_at is not None:
        expires = request.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires.astimezone(UTC).isoformat()
    if request.ttl_seconds is not None:
        return (now + timedelta(seconds=request.ttl_seconds)).isoformat()
    return None
```

(b) Drop the reason requirement (delete the lines 342–346 block):

```python
    symbol = _clean_symbol(request.symbol)
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol_required")
```

(c) In the `include`/`exclude` branches, `expires_at` may now be `None` — that is
already fine (`include[symbol]["expires_at"] = _override_expiry(...)` stores
`None`; the event mirrors it). No further change to those dict literals.

(d) Make the overrides-key TTL cover permanent picks. Replace line 391:

```python
    _redis_set_json(
        redis,
        _keys()["overrides"],
        next_overrides,
        _overrides_key_ttl(next_overrides, _ttl()["overrides"]),
    )
```

Add a helper near `_effective_snapshot_ttl`:

```python
def _overrides_key_ttl(overrides: dict[str, Any], default_ttl: int) -> int:
    """TTL for the overrides key.

    If any active override is permanent (no ``expires_at``), the key must not
    expire — return a long horizon so permanent operator picks survive. Otherwise
    keep at least the default and extend to the furthest explicit expiry.
    """
    now = datetime.now(UTC)
    max_expiry_ttl = 0
    has_permanent = False
    for bucket in ("manual_include", "manual_exclude"):
        raw_bucket = overrides.get(bucket)
        if not isinstance(raw_bucket, dict):
            continue
        for item in raw_bucket.values():
            if not isinstance(item, dict):
                continue
            expires_at = _parse_dt(item.get("expires_at"))
            if expires_at is None:
                has_permanent = True
            else:
                max_expiry_ttl = max(
                    max_expiry_ttl,
                    int((expires_at - now).total_seconds()),
                )
    if has_permanent:
        # ~10 years; effectively non-expiring while remaining a bounded int.
        return 315_360_000
    return max(default_ttl, max_expiry_ttl)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/dashboard/test_universe.py -v`
Expected: all tests PASS (3 new + existing).

**Step 5: Lint**

Run: `ruff check services/dashboard/routes/universe.py && black --check services/dashboard/routes/universe.py`
Expected: clean.

**Step 6: Commit**

```bash
git add services/dashboard/routes/universe.py tests/unit/dashboard/test_universe.py
git commit -m "feat(universe): permanent, reason-optional manual include overrides"
```

---

## Task 2: Backend — `GET /resolve` name-confirmation endpoint

**Files:**
- Modify: `services/dashboard/routes/universe.py`
- Test: `tests/unit/dashboard/test_universe.py`

**Step 1: Write the failing tests**

```python
@pytest.mark.asyncio
async def test_resolve_returns_known_name(monkeypatch):
    universe, _fake = _client(
        monkeypatch,
        {
            "system:trade_targets:latest": {
                "codes": ["005930"],
                "names": {"005930": "삼성전자"},
            },
        },
    )

    body = await universe.resolve_universe_symbol(code="005930")

    assert body == {"code": "005930", "name": "삼성전자", "known": True}


@pytest.mark.asyncio
async def test_resolve_returns_pending_for_unknown_code(monkeypatch):
    universe, _fake = _client(monkeypatch, {})

    body = await universe.resolve_universe_symbol(code="123456")

    assert body == {"code": "123456", "name": None, "known": False}


@pytest.mark.asyncio
async def test_resolve_rejects_bad_code(monkeypatch):
    universe, _fake = _client(monkeypatch, {})

    with pytest.raises(universe.HTTPException) as excinfo:
        await universe.resolve_universe_symbol(code="12ab")
    assert excinfo.value.status_code == 400
```

**Step 2: Run to verify they fail**

Run: `pytest tests/unit/dashboard/test_universe.py -k resolve -v`
Expected: FAIL — `resolve_universe_symbol` does not exist.

**Step 3: Implement**

In `services/dashboard/routes/universe.py`, add a name-map builder that reuses the
same raw sources as `_build_snapshot`, plus the route. Import `extract_names` and
`clean_name` from the package (extend the existing
`from shared.stock_universe import (...)`). If `clean_name`/`extract_names` are not
exported by `shared/stock_universe/__init__.py`, import them from
`shared.stock_universe.effective` directly.

```python
import re

_CODE_RE = re.compile(r"^\d{6}$")


def _build_name_map(redis: Any) -> dict[str, str]:
    """Merge code->name across every raw universe source + open positions."""
    keys = _keys()
    names: dict[str, str] = {}
    for source_key in (
        "screener_universe",
        "trade_targets",
        "daily_watchlist",
        "daily_indicators",
        "theme_targets",
    ):
        payload = decode_payload(_redis_get(redis, keys[source_key]))
        for code, name in extract_names(payload).items():
            names.setdefault(code, name)
    _open_codes, open_names = _read_open_positions()
    for code, name in open_names.items():
        names.setdefault(str(code).strip(), name)
    return names


@router.get("/resolve")
async def resolve_universe_symbol(
    code: str = Query(...),
) -> dict[str, Any]:
    """Resolve a 6-digit code to a display name the system already knows.

    Returns ``known=False`` with ``name=None`` for a valid code the system has
    not seen yet (still addable — the operator confirms by code).
    """
    cleaned = _clean_symbol(code)
    if not _CODE_RE.match(cleaned):
        raise HTTPException(status_code=400, detail="invalid_code")
    name = _build_name_map(_get_redis_client()).get(cleaned)
    return {"code": cleaned, "name": name, "known": name is not None}
```

Note: the test harness's fake `Query` returns its default; calling
`resolve_universe_symbol(code=...)` directly passes the value through, matching the
existing pattern.

**Step 4: Run to verify they pass**

Run: `pytest tests/unit/dashboard/test_universe.py -k resolve -v`
Expected: PASS.

**Step 5: Lint**

Run: `ruff check services/dashboard/routes/universe.py && black --check services/dashboard/routes/universe.py`

**Step 6: Commit**

```bash
git add services/dashboard/routes/universe.py tests/unit/dashboard/test_universe.py
git commit -m "feat(universe): add GET /resolve name-confirmation endpoint"
```

---

## Task 3: Frontend API client — resolve method + types

**Files:**
- Modify: `strategy-builder-ui/src/lib/dashboard/universe.ts`
- Test: `strategy-builder-ui/src/lib/dashboard/universe.test.ts` (create)

**Step 1: Write the failing test**

Create `strategy-builder-ui/src/lib/dashboard/universe.test.ts`. Model it on
`src/lib/dashboard/eventContext.test.ts` (same directory) — match how it mocks
`./client`. General shape:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("./client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
}));

import { apiClient } from "./client";
import { universeApi } from "./universe";

describe("universeApi.resolve", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls the resolve endpoint with the code param", async () => {
    (apiClient.get as any).mockResolvedValue({
      data: { code: "005930", name: "삼성전자", known: true },
    });

    const res = await universeApi.resolve("005930");

    expect(apiClient.get).toHaveBeenCalledWith(
      "/api/trading/universe/resolve",
      { params: { code: "005930" } },
    );
    expect(res.data.known).toBe(true);
  });
});
```

**Step 2: Run to verify it fails**

Run: `cd strategy-builder-ui && npx vitest run src/lib/dashboard/universe.test.ts`
Expected: FAIL — `universeApi.resolve` is not a function.

**Step 3: Implement**

In `strategy-builder-ui/src/lib/dashboard/universe.ts` add the type and method:

```ts
export interface UniverseResolveResponse {
  code: string;
  name: string | null;
  known: boolean;
}
```

Add to the `universeApi` object:

```ts
  resolve: (code: string) =>
    apiClient.get<UniverseResolveResponse>('/api/trading/universe/resolve', {
      params: { code },
    }),
```

**Step 4: Run to verify it passes**

Run: `cd strategy-builder-ui && npx vitest run src/lib/dashboard/universe.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add strategy-builder-ui/src/lib/dashboard/universe.ts strategy-builder-ui/src/lib/dashboard/universe.test.ts
git commit -m "feat(universe-ui): resolve() api client method + type"
```

---

## Task 4: Frontend — split My List vs System-found (page restructure)

This task has no unit test of its own for layout; correctness is covered by Task 5
(the add flow) and a render smoke test here. Keep it a focused refactor.

**Files:**
- Modify: `strategy-builder-ui/src/app/universe/page.tsx`

**Step 1: Derive the two sets**

In `UniversePage`, after `data` is available, split rows by origin. A row belongs
to **My List** when it is a manual include. The row model exposes
`override === "manual_include"` (see `UniverseRow.override` in `universe.ts`).

```tsx
const myList = useMemo(
  () => (data?.rows ?? []).filter((r) => r.override === "manual_include"),
  [data],
);
const systemRows = useMemo(
  () => (data?.rows ?? []).filter((r) => r.override !== "manual_include"),
  [data],
);
```

**Step 2: Update the stat row**

Replace the "Manual Blocks" tile with a "My List" count and add an effective-total
tile:

```tsx
<StatCell label="My List" value={`${myList.length}`} />
<StatCell label="System Found" value={`${systemRows.length}`} />
<StatCell label="Effective" value={`${activeCount}/${data?.max_symbols ?? 0}`} />
<StatCell label="Stale Sources" value={`${staleSources}`} />
```

Remove the now-unused `blockedCount` memo.

**Step 3: Region A — My List section (above System-found)**

Add a `MyListTable` component (a trimmed `UniverseTable`): columns Symbol
(`SymbolLabel`), Entry state (`StateBadge` on `new_entries_allowed`), Added
(`fmtDateTime(row.override_detail?.created_at)`), and a single **Remove** action
button (Trash2) calling `onRowAction(row, "remove")`. No Pin/Block buttons here.
Empty state copy: `아직 추가한 종목이 없습니다 — 위에서 추가하세요`.

The add box (Task 5) renders at the top of this section.

**Step 4: Region B — System-found section**

Reuse the existing `UniverseTable` for `systemRows`, but drop the Pin/Block/Remove
action column for system rows OR keep only "Pin to My List" (include). Recommended
minimal: keep a single **Pin** button that calls `onRowAction(row, "include")` so
the operator can promote a system find into My List. Remove the Block (Ban) button
entirely (no block-list UI per design). Update the `UniverseTable` header/cells
accordingly, or pass a prop to toggle which actions render.

Keep the Source Freshness section and Recompute button as they are.

**Step 5: Run render smoke + lint**

Run: `cd strategy-builder-ui && npm run lint`
Expected: clean (no unused imports — remove `Ban` if no longer used).

Add a minimal render test `src/app/universe/page.test.tsx` modeled on
`src/app/market/market.smoke.test.tsx` asserting the page renders "My List" and
"System Found" headings with mocked `universeApi`.

Run: `cd strategy-builder-ui && npx vitest run src/app/universe/page.test.tsx`
Expected: PASS.

**Step 6: Commit**

```bash
git add strategy-builder-ui/src/app/universe/
git commit -m "feat(universe-ui): separate My List from system-found universe"
```

---

## Task 5: Frontend — frictionless add box (type code → confirm name → add)

**Files:**
- Modify: `strategy-builder-ui/src/app/universe/page.tsx`
- Test: `strategy-builder-ui/src/app/universe/page.test.tsx`

**Step 1: Write the failing test(s)**

Extend `src/app/universe/page.test.tsx`. Mock `universeApi.resolve` and
`universeApi.updateOverride`. Assert:
- Typing a 6-digit code triggers `resolve` (debounced) and shows the resolved name.
- A non-6-digit code disables the Add button.
- Clicking Add calls `updateOverride` with `{action: "include", symbol,
  name, operator: "dashboard"}` and NO `ttl_seconds` (permanent).
- An unknown code (`known: false`) still allows Add and shows the pending label.

Use `@testing-library/react` + `userEvent` (already used by existing tests). Fake
timers for the debounce, or set debounce to 0 in test via the component reading a
constant.

**Step 2: Run to verify it fails**

Run: `cd strategy-builder-ui && npx vitest run src/app/universe/page.test.tsx`
Expected: FAIL — new add box not present.

**Step 3: Implement the add box**

Replace the old override `<section>` (current lines ~428–501: Symbol/Name/Reason/
Hours + Pin/Block/Remove) with a compact add box at the top of the My List
section. State:

```tsx
const [addCode, setAddCode] = useState("");
const [resolved, setResolved] = useState<UniverseResolveResponse | null>(null);
const [resolving, setResolving] = useState(false);
const codeValid = /^\d{6}$/.test(addCode.trim());
```

Debounced resolve on `addCode` change (300ms) when `codeValid`; store result in
`resolved`, clear when invalid. Render:
- One text input (`inputMode="numeric"`, maxLength 6, mono), placeholder `005930`.
- A confirmation line:
  - `codeValid && resolved?.known` → green check + `resolved.name · addCode`.
  - `codeValid && resolved && !resolved.known` → muted `이름 확인 예정 · {addCode}`.
  - `!codeValid && addCode` → rose error `6자리 종목코드를 입력하세요`.
- An **Add** button (`+ 추가`), disabled unless `codeValid` (allow add even when
  `!known`).

On Add, reuse the existing `mutation` (`universeApi.updateOverride`), sending:

```tsx
mutation.mutate({
  action: "include",
  symbol: addCode.trim(),
  name: resolved?.name ?? undefined,
  operator: "dashboard",
  // no ttl_seconds → permanent
});
```

On success, clear `addCode`/`resolved` (extend the existing `mutation.onSuccess`).
Optimistic insert is optional — the mutation returns the fresh snapshot and
`setQueryData` already updates the list; keep that behavior (it appears immediately
after the round-trip). Do NOT add a reason field (optional "메모 추가" is a
nice-to-have; skip for YAGNI unless trivial).

Remove now-dead state: `symbol`, `name`, `reason`, `ttlHours`, and the old `submit`
signature that required a reason. Keep `onRowAction` for Remove/Pin (it calls
`mutation.mutate` with `action` and no reason — verify it no longer sends
`ttl_seconds` for includes so pins are permanent too; for `remove` ttl is
irrelevant).

**Step 4: Run to verify it passes**

Run: `cd strategy-builder-ui && npx vitest run src/app/universe/page.test.tsx`
Expected: PASS.

**Step 5: Lint + typecheck + build**

Run: `cd strategy-builder-ui && npm run lint && npm run build`
Expected: clean build.

**Step 6: Commit**

```bash
git add strategy-builder-ui/src/app/universe/
git commit -m "feat(universe-ui): frictionless code->confirm->add flow"
```

---

## Task 6: Full verification pass

**Step 1: Backend suite (hermetic)**

Run: `pytest tests/unit/dashboard/test_universe.py tests/unit/stock_strategy/test_effective_universe.py -v`
Expected: all PASS. This confirms neither the effective-universe computation nor
the exclude path regressed.

**Step 2: Backend lint/type**

Run: `ruff check services/dashboard/routes/universe.py && black --check services/dashboard/routes/universe.py && mypy services/dashboard/routes/universe.py --ignore-missing-imports --no-error-summary`
Expected: clean (mypy: no new errors).

**Step 3: Frontend suite + build**

Run: `cd strategy-builder-ui && npm run test && npm run lint && npm run build`
Expected: all PASS, clean build.

**Step 4: Manual behavioral check (drive the real page)**

Per the repo `verify` habit and the memory note "verify on paper server, not local
cron" — the universe page reads live Redis. If a dashboard is reachable, load
`/universe`, add a code (e.g. a liquid name the screener has seen → expect name
confirmation; an unseen valid code → expect "이름 확인 예정"), confirm it lands in
My List, and confirm Remove drops it. If no live backend is available locally,
note that the vitest page test + backend unit tests are the substitute evidence and
defer the live check to the 모의투자 server.

**Step 5: Commit any fixes, then finish the branch**

Use superpowers:finishing-a-development-branch to decide merge/PR.

---

## Notes for the executor

- **Do not** change `build_effective_universe_snapshot` or the effective-universe
  math. Trading behavior must be identical.
- **Do not** remove the backend `exclude` action — it stays dormant.
- Keep permanent-include as the documented Redis-TTL exception; do not add a
  blanket TTL back onto the overrides key.
- If `extract_names`/`clean_name` aren't exported from
  `shared/stock_universe/__init__.py`, import from
  `shared.stock_universe.effective`.
- Frequent commits: one per task as specified.
