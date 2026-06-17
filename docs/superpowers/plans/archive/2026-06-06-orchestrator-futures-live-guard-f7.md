# Orchestrator Futures Live-Mode Guard (F-7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `LiveModeGuard` into the monolithic orchestrator's real-order **entry** branch for futures, so a real futures entry is refused unless `futures_live.enabled` is true AND not runtime-suspended — closing the gap where the actual futures trade path ignores the live-money gate.

**Architecture:** One small async predicate `_real_entry_blocked()` (futures-only, fail-closed) gates the `OrderExecutor` entry branch in `_place_entry_order`. The guard + a dedicated async Redis handle are built for futures in `_init_execution_layer`. Default `futures_live.enabled=false` ⇒ all real futures entries are blocked, which matches today's paper-only reality. `paper_trading=True` (VirtualBroker), exits, and non-futures paths are untouched.

**Tech Stack:** Python 3.11+ asyncio, `redis.asyncio` + `fakeredis.aioredis` (tests), `LiveModeGuard` (existing), pytest. Tests use the established unbound-method + fake-self pattern (see `tests/unit/trading/test_orchestrator_notify.py`).

**Spec:** `docs/superpowers/specs/2026-06-06-orchestrator-futures-live-guard-f7-design.md`

**Worktree:** Implement in `/tmp/f7-impl` (branch `feat/orchestrator-futures-live-guard`). Run venv tools from `cd /tmp/f7-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**PR strategy:** One PR (`feat/orchestrator-futures-live-guard`).

**Out of scope:** local-DB orderbook / paper-engine changes (already satisfied); gating exit real orders (§4 of spec — exits can't fire without a guarded entry); the order_router daemon (already gated); `LiveModeGuard`/`futures_live.yaml` changes (consumed unchanged).

---

## File Structure

**Modify:** `services/trading/orchestrator.py`
- `__init__` attribute region (~line 792, near `self._order_executor = None`): add `self._live_mode_guard` + `self._guard_redis` defaults.
- `_init_execution_layer` (ends ~line 2030, before `async def _load_swing_positions`): build the guard + redis for futures.
- Add method `_real_entry_blocked()` (near `_place_entry_order`).
- `_place_entry_order` real branch (line 6838, `if self._order_executor is not None:` — the ENTRY one, identifiable by the following `side = OrderSide.SELL if is_short else OrderSide.BUY`): insert the guard.

**Create:** `tests/unit/trading/test_orchestrator_live_guard.py`

**Verified anchors:** `_place_entry_order(self, *, code, is_short, quantity, order_type, limit_price, market_price, price_source_time=None) -> tuple[bool, float, int, str]` (line 6789); paper branch `if self.config.paper_trading and self._paper_broker:` (6800); real branch `if self._order_executor is not None:` (6838). Not-filled tuple shape: `False, 0.0, 0, "KRX"` (used at 6805). `_schedule_notify(message)` exists (7789, fire-and-forget). The exit branch is `elif self._order_executor is not None:` with `side = OrderSide.BUY if is_buy` (7353) — DO NOT touch it. `LiveModeGuard.from_yaml()` + `async is_live_suspended(redis)` (`shared/execution/live_mode_guard.py`).

---

## Task 1: Live-mode guard predicate + entry-branch wiring + tests

**Files:**
- Modify: `services/trading/orchestrator.py`
- Test: `tests/unit/trading/test_orchestrator_live_guard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/trading/test_orchestrator_live_guard.py`:

```python
"""F-7: orchestrator futures live-mode guard on the real-order entry branch."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from services.trading.orchestrator import TradingOrchestrator
from shared.execution.live_mode_guard import LiveModeGuard


def _guard(enabled: bool) -> LiveModeGuard:
    return LiveModeGuard(enabled=enabled)


def _redis() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(db=1)


# ---- _real_entry_blocked matrix (asset gating + guard, fail-closed) ----

@pytest.mark.asyncio
async def test_blocked_futures_when_disabled() -> None:
    fake = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=_guard(False),
        _guard_redis=_redis(),
    )
    assert await TradingOrchestrator._real_entry_blocked(fake) is True


@pytest.mark.asyncio
async def test_allowed_futures_when_enabled_and_not_suspended() -> None:
    fake = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=_guard(True),
        _guard_redis=_redis(),
    )
    assert await TradingOrchestrator._real_entry_blocked(fake) is False


@pytest.mark.asyncio
async def test_blocked_futures_when_redis_suspend_set() -> None:
    r = _redis()
    await r.set("futures:live:suspended", "1")
    fake = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=_guard(True),
        _guard_redis=r,
    )
    assert await TradingOrchestrator._real_entry_blocked(fake) is True


@pytest.mark.asyncio
async def test_blocked_futures_fail_closed_when_guard_or_redis_none() -> None:
    f1 = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=None,
        _guard_redis=_redis(),
    )
    f2 = SimpleNamespace(
        config=SimpleNamespace(asset_class="futures"),
        _live_mode_guard=_guard(True),
        _guard_redis=None,
    )
    assert await TradingOrchestrator._real_entry_blocked(f1) is True
    assert await TradingOrchestrator._real_entry_blocked(f2) is True


@pytest.mark.asyncio
async def test_not_blocked_for_stock_regardless_of_guard() -> None:
    # asset gating: the futures guard never blocks a non-futures entry
    fake = SimpleNamespace(
        config=SimpleNamespace(asset_class="stock"),
        _live_mode_guard=_guard(False),
        _guard_redis=_redis(),
    )
    assert await TradingOrchestrator._real_entry_blocked(fake) is False


# ---- _place_entry_order real branch honors the guard ----

@pytest.mark.asyncio
async def test_entry_real_branch_blocked_for_futures_when_suspended() -> None:
    executor = AsyncMock()
    notes: list[str] = []
    fake = SimpleNamespace(
        config=SimpleNamespace(paper_trading=False, asset_class="futures"),
        _paper_broker=None,
        _order_executor=executor,
        _live_mode_guard=_guard(False),  # disabled -> blocked
        _guard_redis=_redis(),
        _schedule_notify=lambda msg: notes.append(msg),
    )

    result = await TradingOrchestrator._place_entry_order(
        fake,
        code="101W09",
        is_short=False,
        quantity=1,
        order_type="market",
        limit_price=None,
        market_price=100.0,
    )

    assert result == (False, 0.0, 0, "KRX")  # not-filled, no real order
    executor.execute_order.assert_not_awaited()  # real order never placed
    assert notes and "101W09" in notes[0]  # operator alerted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /tmp/f7-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/trading/test_orchestrator_live_guard.py -v`
Expected: FAIL (`AttributeError: ... has no attribute '_real_entry_blocked'`).

- [ ] **Step 3: Add the `__init__` attribute defaults**

In `services/trading/orchestrator.py`, in the `__init__` attribute block, find:
```python
        self._order_executor: Any | None = None
```
Add immediately after it:
```python
        # F-7: futures live-mode gate for the real-order entry path. Built for
        # futures in _init_execution_layer; None for non-futures (never consulted).
        self._live_mode_guard: Any | None = None
        self._guard_redis: Any | None = None
```

- [ ] **Step 4: Build the guard for futures in `_init_execution_layer`**

In `_init_execution_layer`, at the END of the method (immediately before `async def _load_swing_positions`), add:
```python
        # F-7: build the futures live-mode guard + a dedicated async Redis handle.
        # Always built for futures so the real-order path is fail-closed by default
        # (futures_live.enabled defaults to False -> all real entries blocked until
        # the operator completes Phase-5 Gate 3 and enables live).
        if self.config.asset_class == "futures":
            import redis.asyncio as aioredis

            from shared.execution.live_mode_guard import LiveModeGuard

            self._live_mode_guard = LiveModeGuard.from_yaml()
            self._guard_redis = aioredis.from_url(
                os.environ.get("REDIS_URL", "redis://localhost:6379/1")
            )
            logger.info(
                "F-7 futures live-mode guard active (enabled=%s, suspend_key=%s)",
                self._live_mode_guard.enabled,
                self._live_mode_guard.suspend_key,
            )
```

- [ ] **Step 5: Add the `_real_entry_blocked` predicate**

Add this method to `TradingOrchestrator`, immediately above `async def _place_entry_order` (line ~6789):
```python
    async def _real_entry_blocked(self) -> bool:
        """True if a real (non-paper) ENTRY order must be refused (F-7).

        Futures-only: the live-money gate (``futures_live.enabled`` + the Redis
        ``futures:live:suspended`` flag) applies to the orchestrator's real-order
        entry path the same way it gates the order_router daemon. Fail-closed: a
        missing guard/redis handle, or a Redis read error, returns True (block).
        Non-futures assets are never blocked here.
        """
        if self.config.asset_class != "futures":
            return False
        guard = self._live_mode_guard
        redis = self._guard_redis
        if guard is None or redis is None:
            return True
        return await guard.is_live_suspended(redis)
```

- [ ] **Step 6: Insert the guard into the `_place_entry_order` real branch**

In `_place_entry_order`, find the ENTRY real branch (it is followed by `side = OrderSide.SELL if is_short else OrderSide.BUY` — this distinguishes it from the exit branch which uses `is_buy`):
```python
        if self._order_executor is not None:
            from shared.execution.models import OrderRequest, OrderSide, OrderType

            side = OrderSide.SELL if is_short else OrderSide.BUY
```
Insert the guard as the first statements inside that `if`, before the `from shared.execution.models import ...`:
```python
        if self._order_executor is not None:
            if await self._real_entry_blocked():
                logger.warning(
                    "futures live suspended — real ENTRY blocked for %s "
                    "(enable: set futures_live.enabled=true + clear the redis "
                    "suspend key)",
                    code,
                )
                self._schedule_notify(
                    f"⛔ 선물 실주문 차단 (live suspended): {code} — "
                    "futures_live.enabled / futures:live:suspended 확인"
                )
                return False, 0.0, 0, "KRX"

            from shared.execution.models import OrderRequest, OrderSide, OrderType

            side = OrderSide.SELL if is_short else OrderSide.BUY
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd /tmp/f7-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/trading/test_orchestrator_live_guard.py -v`
Expected: PASS (6 passed).

- [ ] **Step 8: Format + mypy + commit**

```bash
cd /tmp/f7-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/trading/orchestrator.py tests/unit/trading/test_orchestrator_live_guard.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/trading/orchestrator.py tests/unit/trading/test_orchestrator_live_guard.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy services/trading/orchestrator.py 2>&1 | tail -5
git add services/trading/orchestrator.py tests/unit/trading/test_orchestrator_live_guard.py
git commit -m "feat(f-7): live-mode guard on orchestrator futures real-entry path"
```
Note: `orchestrator.py` has many PRE-EXISTING mypy errors — confirm the 3 new pieces (`_real_entry_blocked`, the guard build, the `_place_entry_order` insertion) introduce NO new errors (none mentioning `_real_entry_blocked`/`_live_mode_guard`/`_guard_redis`).

---

## Task 2: Full gate + PR

- [ ] **Step 1: Targeted + regression**

```bash
cd /tmp/f7-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/trading/test_orchestrator_live_guard.py tests/unit/trading/test_orchestrator_notify.py -v
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -k "live_mode or live_guard or order_router" -q
```
Expected: all PASS (the second confirms the unchanged `LiveModeGuard` + order_router still pass).

- [ ] **Step 2: Full gate (CI parity)**

```bash
cd /tmp/f7-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q
```
Expected: green (F-7 adds a default-block guard on the futures real path; paper/stock/existing tests unaffected).

- [ ] **Step 3: Push + PR**

```bash
cd /tmp/f7-impl
git push -u origin feat/orchestrator-futures-live-guard
gh pr create --base main --head feat/orchestrator-futures-live-guard \
  --title "feat(f-7): live-mode guard on orchestrator futures real-entry path" \
  --body "$(cat <<'EOF'
## What
Wire `LiveModeGuard` into the monolithic orchestrator's real-order **entry** branch
for futures (`_place_entry_order`), so a real futures entry is refused unless
`futures_live.enabled` is true AND `futures:live:suspended` is not set.

## Why (safety gap)
Futures trades today via the orchestrator (in-process). Its real-order path had
**zero** `LiveModeGuard` references — the two-layer live-money gate was checked only
in the dormant `order_router` daemon, NOT the path that actually trades futures. So a
misconfigured real run (`paper_trading=False` + real creds) could place real orders
with `futures_live.enabled=false`. F-7 closes that gap.

## Approach — entries-only, futures-only, fail-closed, merge-safe
A small async predicate `_real_entry_blocked()` (futures-only; fail-closed on missing
guard/redis or redis error) gates the `OrderExecutor` entry branch. Default
`futures_live.enabled=false` ⇒ all real futures entries blocked — which **matches
today's paper-only reality** (futures paper-only until Phase-5 Gate 3), so merging
changes nothing operationally; it enforces the intended state in the actual trade path.
Exits are NOT gated (they close existing real risk and cannot fire without a guarded
entry). `paper_trading=True` (VirtualBroker — the operator's real-data+local-paper
model) and non-futures paths are untouched. The order_router daemon, `LiveModeGuard`,
and `futures_live.yaml` are unchanged — both execution paths now honor the same gate.

## How tested
Unit (`tests/unit/trading/test_orchestrator_live_guard.py`, unbound-method + fake-self
pattern): `_real_entry_blocked` matrix (futures+disabled→block, futures+enabled→allow,
redis-suspend→block, guard/redis None→block fail-closed, stock→never block); and
`_place_entry_order` real branch returns not-filled + never calls `execute_order` +
alerts when blocked. Regression (`LiveModeGuard`/order_router unchanged) + full `tests/`
gate green.

## Going live (later, Phase-5 Gate 3)
`futures_live.enabled=true` + `redis-cli -n 1 del futures:live:suspended` → real entries
allowed (same gate the order_router uses).

Spec: `docs/superpowers/specs/2026-06-06-orchestrator-futures-live-guard-f7-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-06-orchestrator-futures-live-guard-f7.md`

## Follow-ups
The broader futures decoupling roadmap (F-1 stream-naming coherence, F-3 order_router
paper mode + orderbook transport, F-5 monitor, F-8/F-9 cutover) remains — see the
futures-decoupling assessment.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §5.1 guard + redis injection (init defaults + build for futures in `_init_execution_layer`) → Task 1 Steps 3-4. ✓
- §5.2 testable predicate → Task 1 Step 5 (`_real_entry_blocked`, which folds the spec's asset check + `_live_order_suspended` into one testable method — a testability refinement; behavior identical to the spec). ✓
- §5.3 guard placement in `_place_entry_order` entry real branch → Task 1 Step 6. ✓
- §5.4 behavior (default-block, paper unaffected, asset!=futures unaffected, live-flip) → covered by `_real_entry_blocked` (asset gate + guard) + the paper branch being untouched. ✓
- §4 entries-only (exit branch untouched) → Task 1 only edits the entry branch (the `is_short` one); the `is_buy` exit branch is explicitly not touched. ✓
- §6 fail-closed + log + best-effort notify → `_real_entry_blocked` returns True on None/error; the guard block logs WARNING + `_schedule_notify` (fire-and-forget). ✓
- §7 testing (predicate matrix incl. stock asset-gating + fail-closed; entry-branch blocked path) → Task 1 Step 1 (6 tests). ✓
- §8 acceptance → Tasks 1-2. ✓

**Placeholder scan:** none — complete code in every step.

**Type consistency:** `_real_entry_blocked(self) -> bool` and the `_place_entry_order` return tuple `(bool, float, int, str)` = `(False, 0.0, 0, "KRX")` match across method, guard insertion, and the test assertion. `_live_mode_guard`/`_guard_redis` attribute names are identical in `__init__`, `_init_execution_layer`, `_real_entry_blocked`, and the tests. `LiveModeGuard(enabled=...)` + `is_live_suspended(redis)` + `suspend_key`/`enabled` fields match `shared/execution/live_mode_guard.py`. `_schedule_notify(message)` matches line 7789. The entry-branch anchor (`side = OrderSide.SELL if is_short`) is unique vs the exit branch (`is_buy`), so the edit can't hit the wrong branch.

**Naming note vs spec:** the spec named the helper `_live_order_suspended` (guard-only) with the asset check inline at the call site; the plan uses `_real_entry_blocked` (asset + guard folded) for clean unbound-method testability. Same behavior, better test surface. The PR/spec acceptance criteria are all still met.

**Open questions resolved:** guard redis = dedicated `aioredis.from_url` built for futures in `_init_execution_layer` (not the conditional `_stream_redis`); notify = `_schedule_notify` (fire-and-forget, exists); test location = new `tests/unit/trading/test_orchestrator_live_guard.py`; exit branch explicitly untouched (§4).
