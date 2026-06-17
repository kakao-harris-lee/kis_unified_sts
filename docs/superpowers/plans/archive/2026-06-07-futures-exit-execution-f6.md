# Futures Decoupled Exit Execution (F-6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the decoupled futures chain actually close positions by driving the already-built PseudoOCO brackets from an order_router exit-monitor — paper = simulated fills + shadow risk-state; live = real market exit orders (guard-blocked) + live risk-state.

**Architecture:** order_router gains a periodic asyncio exit-monitor (started in `on_startup`, cancelled in `on_shutdown`) that polls `KISFuturesPriceFeed.get_current_price` and drives `PseudoOCO.on_tick`/`check_expiry`. PseudoOCO gains an injected close-executor (absent → paper synthetic fill; present → live real order) plus optional `RuntimeRiskState` for realized-PnL recording. `OCOHandle` carries the entry price for PnL.

**Tech Stack:** Python 3.11+ asyncio, Redis streams (fakeredis in tests), pytest. Reuses `KISFuturesAdapter` (F-3), `RuntimeRiskState.key_suffix` (F-1), `LiveModeGuard` (F-7).

**Spec:** `docs/superpowers/specs/2026-06-07-futures-exit-execution-f6-design.md`

**Worktree:** Implement in `/tmp/f6-impl` (branch `feat/futures-exit-execution-f6`). Run venv tools from `cd /tmp/f6-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**GIT HYGIENE (critical):** NEVER run `git stash`/`pop`/`apply`/`drop` — repo-global across worktrees, corrupts the operator's stash. Use `git add <explicit paths>` + `git commit` only. Do not touch `/home/deploy/project/kis_unified_sts`.

**Key decisions:** live exit = MARKET order, **guard-blocked** (suspended → skip + retry, handle stays ACTIVE; documented trade-off: no auto-flatten while suspended). Paper places no real order structurally. Risk: paper→`risk:state:futures:shadow`, live→`risk:state:futures`.

**Out of scope:** separate futures_exit daemon, F-5 monitor, entry-path/risk_filter/decision_engine changes, KIS server-side OCO, auto-flatten-while-suspended.

---

## File Structure

**Modify:**
- `shared/execution/pseudo_oco.py` — `OCOHandle.entry_price`; `PseudoOCO` optional `runtime_state`/`multiplier_krw_per_point`/`close_executor`; `_close` returns bool + records PnL + uses close_executor; `on_tick`/`check_expiry` delete-on-close-only.
- `services/order_router/main.py` — `OrderRouterDaemon` exit-monitor (`__init__` params, `on_startup`, `on_shutdown`, `_exit_monitor_loop`); `_build_and_run` per-mode PseudoOCO/runtime_state/feed wiring.

**Create:**
- `shared/execution/live_exit_executor.py` — `LiveExitExecutor` (real market flatten, guard-blocked).
- `tests/unit/execution/test_live_exit_executor.py`

**Test (modify/extend):**
- `tests/unit/execution/test_pseudo_oco.py` — entry_price, PnL recording, close_executor, back-compat.
- `tests/unit/services/test_order_router_main.py` — exit-monitor loop.
- `tests/integration/test_signal_to_fill_e2e.py` — paper entry→exit lifecycle.

---

## Task 1: PseudoOCO — entry_price, PnL recording, pluggable close

**Files:**
- Modify: `shared/execution/pseudo_oco.py`
- Test: `tests/unit/execution/test_pseudo_oco.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/execution/test_pseudo_oco.py`:
```python
class TestPnLRecording:
    @pytest.mark.asyncio
    async def test_entry_price_stored(self, fill_logger):
        oco = PseudoOCO(fill_logger=fill_logger)
        h = await oco.register_bracket(
            signal=_signal("long"), signal_id="s1", fill=_fill()
        )
        assert h.entry_price == 331.20

    @pytest.mark.asyncio
    async def test_long_stop_records_loss(self, fill_logger):
        rs = AsyncMock()
        oco = PseudoOCO(
            fill_logger=fill_logger, runtime_state=rs, multiplier_krw_per_point=50_000
        )
        await oco.register_bracket(signal=_signal("long"), signal_id="s1", fill=_fill())
        # long entry 331.20, stop 330.00 → loss = (330.00-331.20)*1*1*50000 = -60000
        await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        rs.record_trade.assert_awaited_once()
        assert rs.record_trade.await_args.kwargs["pnl_krw"] == pytest.approx(-60_000.0)
        rs.record_loss.assert_awaited_once()
        rs.record_win.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_long_target_records_win(self, fill_logger):
        rs = AsyncMock()
        oco = PseudoOCO(
            fill_logger=fill_logger, runtime_state=rs, multiplier_krw_per_point=50_000
        )
        await oco.register_bracket(signal=_signal("long"), signal_id="s1", fill=_fill())
        # target 333.00 → win = (333.00-331.20)*50000 = +90000
        await oco.on_tick(symbol="A05603", price=334.0, now_ms=2000)
        assert rs.record_trade.await_args.kwargs["pnl_krw"] == pytest.approx(90_000.0)
        rs.record_win.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_short_stop_records_loss(self, fill_logger):
        rs = AsyncMock()
        oco = PseudoOCO(
            fill_logger=fill_logger, runtime_state=rs, multiplier_krw_per_point=50_000
        )
        await oco.register_bracket(signal=_signal("short"), signal_id="s1", fill=_fill())
        # short entry 331.20, stop 332.40 → loss = (332.40-331.20)*(-1)*1*50000 = -60000
        await oco.on_tick(symbol="A05603", price=333.0, now_ms=2000)
        assert rs.record_trade.await_args.kwargs["pnl_krw"] == pytest.approx(-60_000.0)
        rs.record_loss.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_runtime_state_records_nothing(self, fill_logger):
        oco = PseudoOCO(fill_logger=fill_logger)  # back-compat: no recording
        await oco.register_bracket(signal=_signal("long"), signal_id="s1", fill=_fill())
        fired = await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        assert len(fired) == 1  # still closes
        fill_logger.log_fill.assert_awaited_once()  # still logs


class TestCloseExecutor:
    @pytest.mark.asyncio
    async def test_live_close_uses_real_fill_price(self, fill_logger):
        from shared.execution.passive_maker import Fill

        executor = AsyncMock()
        executor.flatten.return_value = Fill(
            order_id="EXIT-1", price=329.5, quantity=1, filled_at_ms=2000
        )
        rs = AsyncMock()
        oco = PseudoOCO(
            fill_logger=fill_logger, runtime_state=rs,
            multiplier_krw_per_point=50_000, close_executor=executor,
        )
        await oco.register_bracket(signal=_signal("long"), signal_id="s1", fill=_fill())
        fired = await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        assert len(fired) == 1
        executor.flatten.assert_awaited_once()
        assert executor.flatten.await_args.kwargs["side"] == "short"  # flatten a long
        # logged + PnL use the REAL fill price 329.5, not the stop 330.00
        assert fill_logger.log_fill.await_args.kwargs["filled_price"] == 329.5
        assert rs.record_trade.await_args.kwargs["pnl_krw"] == pytest.approx(
            (329.5 - 331.20) * 50_000
        )

    @pytest.mark.asyncio
    async def test_live_close_blocked_keeps_handle_active(self, fill_logger):
        executor = AsyncMock()
        executor.flatten.return_value = None  # guard-blocked / unfilled
        oco = PseudoOCO(fill_logger=fill_logger, close_executor=executor)
        h = await oco.register_bracket(
            signal=_signal("long"), signal_id="s1", fill=_fill()
        )
        fired = await oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
        assert fired == []  # not closed
        assert h.state is OCOState.ACTIVE  # stays active for retry
        fill_logger.log_fill.assert_not_awaited()
        assert len(oco.active_handles) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /tmp/f6-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/execution/test_pseudo_oco.py -q`
Expected: FAIL (entry_price missing / TypeError on new kwargs).

- [ ] **Step 3: Implement**

In `shared/execution/pseudo_oco.py`:

(a) Add a TYPE_CHECKING import (top, after `from __future__ import annotations`):
```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shared.risk.runtime_state import RuntimeRiskState
```

(b) Add `entry_price` to `OCOHandle` (after `quantity`):
```python
    entry_price: float = 0.0
```

(c) Set it in `register_bracket` — add to the `OCOHandle(...)` constructor (after `quantity=fill.quantity,`):
```python
            entry_price=fill.price,
```

(d) Extend `__init__`:
```python
    def __init__(
        self,
        *,
        fill_logger: FillLogger,
        venue: str = "KRX",
        runtime_state: "RuntimeRiskState | None" = None,
        multiplier_krw_per_point: float = 0.0,
        close_executor: Any = None,
    ) -> None:
        self.fill_logger = fill_logger
        self.venue = venue
        self._runtime_state = runtime_state
        self._multiplier = multiplier_krw_per_point
        self._close_executor = close_executor
        self._handles: dict[str, OCOHandle] = {}
        self._next_id: int = 1
```

(e) Replace `_close` to return `bool`, honor the close_executor, and record PnL:
```python
    async def _close(
        self,
        handle: OCOHandle,
        *,
        fill_price: float,
        now_ms: int,
        trade_role: str,
        order_type: str,
        new_state: OCOState,
    ) -> bool:
        """Close a handle. Returns True if closed, False if blocked (retry).

        Paper (no close_executor): synthesize a fill at ``fill_price``.
        Live (close_executor set): place a real order; None return = guard-
        blocked/unfilled → leave the handle ACTIVE for the next poll.
        """
        if self._close_executor is not None:
            real_fill = await self._close_executor.flatten(
                symbol=handle.symbol,
                side=_opposite(handle.direction),
                quantity=handle.quantity,
                requested_price=fill_price,
                now_ms=now_ms,
            )
            if real_fill is None:
                logger.warning(
                    "live exit not placed handle=%s role=%s; will retry",
                    handle.handle_id,
                    trade_role,
                )
                return False
            actual_price = float(real_fill.price)
        else:
            actual_price = fill_price
        # State transition before the log I/O: a re-raised log_fill failure must
        # not leave the handle ACTIVE for a duplicate fire (see PR #134 note).
        handle.state = new_state
        await self.fill_logger.log_fill(
            signal_id=handle.signal_id,
            order_id=f"{handle.handle_id}-{trade_role}",
            symbol=handle.symbol,
            side=_opposite(handle.direction),
            order_type=order_type,
            requested_price=fill_price,
            filled_price=actual_price,
            tick_size_points=handle.tick_size_points,
            slippage_ticks=0.0,
            quantity=handle.quantity,
            requested_at_ms=now_ms,
            filled_at_ms=now_ms,
            venue=self.venue,
            trade_role=trade_role,
        )
        await self._record_pnl(handle, exit_price=actual_price)
        return True

    async def _record_pnl(self, handle: OCOHandle, *, exit_price: float) -> None:
        if self._runtime_state is None or self._multiplier <= 0.0:
            return
        sign = 1.0 if handle.direction == "long" else -1.0
        pnl = (exit_price - handle.entry_price) * sign * handle.quantity * self._multiplier
        await self._runtime_state.record_trade(pnl_krw=pnl)
        if pnl < 0:
            await self._runtime_state.record_loss()
        else:
            await self._runtime_state.record_win()
```

(f) In `on_tick`, gate the `del`/`fired.append` on the `_close` return value. Replace the stop/target blocks:
```python
            if _is_stop_hit(handle, price):
                if await self._close(
                    handle,
                    fill_price=handle.stop_price,
                    now_ms=now_ms,
                    trade_role="stop_loss",
                    order_type="stop",
                    new_state=OCOState.STOP_HIT,
                ):
                    fired.append(handle)
                    del self._handles[handle_id]
            elif _is_target_hit(handle, price):
                if await self._close(
                    handle,
                    fill_price=handle.target_price,
                    now_ms=now_ms,
                    trade_role="take_profit",
                    order_type="limit_passive",
                    new_state=OCOState.TARGET_HIT,
                ):
                    fired.append(handle)
                    del self._handles[handle_id]
```

(g) In `check_expiry`, gate similarly:
```python
                if await self._close(
                    handle,
                    fill_price=fill_price,
                    now_ms=now_ms,
                    trade_role="force_close",
                    order_type="market",
                    new_state=OCOState.EXPIRED,
                ):
                    expired.append(handle)
                    del self._handles[handle_id]
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /tmp/f6-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/execution/test_pseudo_oco.py -q`
Expected: PASS (existing 16 + new tests). The existing on_tick/check_expiry tests still pass (paper path: `_close` returns True → same close+del behavior; `filled_price` still equals the trigger price).

- [ ] **Step 5: Format + mypy + commit**

```bash
cd /tmp/f6-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black shared/execution/pseudo_oco.py tests/unit/execution/test_pseudo_oco.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix shared/execution/pseudo_oco.py tests/unit/execution/test_pseudo_oco.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/execution/pseudo_oco.py
git add shared/execution/pseudo_oco.py tests/unit/execution/test_pseudo_oco.py
git commit -m "feat(f-6): PseudoOCO entry_price + PnL recording + pluggable close executor"
```

---

## Task 2: order_router exit-monitor + paper wiring

**Files:**
- Modify: `services/order_router/main.py`
- Test: `tests/unit/services/test_order_router_main.py`

- [ ] **Step 1: Write failing test**

Append to `tests/unit/services/test_order_router_main.py` (reuse existing `_spec`/`_signal`/`redis`/`fakeredis` helpers; add imports as needed at top: `from shared.execution.pseudo_oco import PseudoOCO`, `from shared.execution.fill_logger import FillLogger`, `from shared.execution.passive_maker import Fill`):
```python
class _FakeFeed:
    def __init__(self, close: float) -> None:
        self._close = close

    async def get_current_price(self, symbol: str) -> dict:
        return {"close": self._close}


@pytest.mark.asyncio
async def test_exit_monitor_closes_bracket_and_records_pnl(redis):
    fill_logger = FillLogger(redis=redis, stream="order.fill.futures.shadow", batch_size=1)
    runtime_state = AsyncMock()
    pseudo_oco = PseudoOCO(
        fill_logger=fill_logger, runtime_state=runtime_state,
        multiplier_krw_per_point=50_000,
    )
    # register a long bracket: entry 331.20, stop 330.00
    await pseudo_oco.register_bracket(
        signal=_signal("long"), signal_id="s1",
        fill=Fill(order_id="E1", price=331.20, quantity=1, filled_at_ms=1000),
    )
    daemon = OrderRouterDaemon(
        redis=redis,
        passive_maker=AsyncMock(),
        pseudo_oco=pseudo_oco,
        contract_spec=_spec(),
        final_stream="signal.final.futures.shadow",
        consumer_group="order_router",
        worker_id="w1",
        xread_block_ms=100,
        batch_size=1,
        passive_timeout_seconds=1,
        locked_symbol="A05603",
        futures_price_feed=_FakeFeed(close=329.0),  # below the stop → fires
        exit_poll_interval=0.01,
    )
    await daemon.on_startup()
    await asyncio.sleep(0.05)  # let the monitor poll at least once
    await daemon.on_shutdown()
    assert pseudo_oco.active_handles == []  # bracket closed
    runtime_state.record_trade.assert_awaited()  # PnL recorded


@pytest.mark.asyncio
async def test_no_feed_starts_no_monitor(redis):
    daemon = OrderRouterDaemon(
        redis=redis, passive_maker=AsyncMock(), pseudo_oco=AsyncMock(),
        contract_spec=_spec(), final_stream="signal.final.futures",
        consumer_group="order_router", worker_id="w1", xread_block_ms=100,
        batch_size=1, passive_timeout_seconds=1, locked_symbol="A05603",
    )
    await daemon.on_startup()
    assert daemon._exit_task is None
    await daemon.on_shutdown()  # no-op, must not raise
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /tmp/f6-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/services/test_order_router_main.py -q`
Expected: FAIL (`OrderRouterDaemon` has no `futures_price_feed`/`exit_poll_interval`/`_exit_task`).

- [ ] **Step 3: Implement the daemon exit-monitor**

In `services/order_router/main.py`, `OrderRouterDaemon.__init__` — add two params at the end of the signature (after `locked_symbol: str | None = None,`):
```python
        futures_price_feed: Any = None,
        exit_poll_interval: float = 1.0,
```
and store them + the task handle (after `self.locked_symbol = locked_symbol`):
```python
        self.futures_price_feed = futures_price_feed
        self.exit_poll_interval = exit_poll_interval
        self._exit_task: asyncio.Task[None] | None = None
        self.exits_fired_count: int = 0
```

Extend `on_startup` — at the end of the method, after the sentinel block:
```python
        if self.futures_price_feed is not None and not self.refused_due_to_sentinel:
            self._exit_task = asyncio.create_task(self._exit_monitor_loop())
```

Add `on_shutdown` + the loop (new methods on the class):
```python
    async def on_shutdown(self) -> None:
        if self._exit_task is not None:
            self._exit_task.cancel()
            try:
                await self._exit_task
            except asyncio.CancelledError:
                pass
            self._exit_task = None

    async def _exit_monitor_loop(self) -> None:
        """Poll the live feed and drive PseudoOCO stop/target/expiry closes.

        KIS server-side OCO is restricted, so brackets are monitored client-
        side here. Paper closes are synthetic; live closes place real orders
        via the PseudoOCO close_executor. Resilient: a bad iteration is logged
        and retried so the consume loop and feed stay alive.
        """
        while not self._stop.is_set():
            try:
                price = await self.futures_price_feed.get_current_price(
                    self.locked_symbol
                )
                close = price.get("close") if price else None
                now_ms = int(datetime.now(UTC).timestamp() * 1000)
                if close is not None:
                    fired = await self.pseudo_oco.on_tick(
                        symbol=self.locked_symbol,
                        price=float(close),
                        now_ms=now_ms,
                    )
                    self.exits_fired_count += len(fired)
                expired = await self.pseudo_oco.check_expiry(
                    now_ms=now_ms,
                    market_price=float(close) if close is not None else None,
                )
                self.exits_fired_count += len(expired)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("exit-monitor iteration failed; continuing")
            try:
                await asyncio.sleep(self.exit_poll_interval)
            except asyncio.CancelledError:
                raise
```
(`datetime`/`UTC` are already imported at module top; `Any` is imported; `asyncio` is imported.)

- [ ] **Step 4: Wire the paper branch in `_build_and_run`**

Add to the local imports inside `_build_and_run` (with the other `from shared.execution...` imports):
```python
    from shared.risk.runtime_state import RuntimeRiskState
```

Replace the mode branch's tail + the single `pseudo_oco = PseudoOCO(fill_logger=fill_logger)` line. In the `if mode == "paper":` branch add (after `guard_for_daemon = None`):
```python
        exit_runtime_state: Any = RuntimeRiskState(
            redis=redis_client, asset_class="futures", key_suffix="shadow"
        )
        exit_close_executor: Any = None  # paper: synthetic fills, no real orders
        exit_feed: Any = futures_feed
```
In the `else:  # live` branch add (after `guard_for_daemon = live_guard`):
```python
        # Live exit-monitor wiring is added in F-6 Task 3 (LiveExitExecutor).
        exit_runtime_state = None
        exit_close_executor = None
        exit_feed = None
```
Replace `pseudo_oco = PseudoOCO(fill_logger=fill_logger)` with:
```python
    pseudo_oco = PseudoOCO(
        fill_logger=fill_logger,
        runtime_state=exit_runtime_state,
        multiplier_krw_per_point=spec.multiplier_krw_per_point,
        close_executor=exit_close_executor,
    )
```
Add to the `OrderRouterDaemon(...)` call (after `locked_symbol=symbol,`):
```python
        futures_price_feed=exit_feed,
```

- [ ] **Step 5: Run to verify it passes + regression**

```bash
cd /tmp/f6-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/services/test_order_router_main.py tests/unit/execution/ -q
```
Expected: PASS (new exit-monitor tests + F-1/F-3 helper tests + execution suites).

- [ ] **Step 6: Format + commit**

```bash
cd /tmp/f6-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/order_router/main.py tests/unit/services/test_order_router_main.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/order_router/main.py tests/unit/services/test_order_router_main.py
git add services/order_router/main.py tests/unit/services/test_order_router_main.py
git commit -m "feat(f-6): order_router exit-monitor poll task + paper wiring (shadow risk-state)"
```

---

## Task 3: LiveExitExecutor + live wiring

**Files:**
- Create: `shared/execution/live_exit_executor.py`
- Modify: `services/order_router/main.py` (live branch)
- Test: `tests/unit/execution/test_live_exit_executor.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/execution/test_live_exit_executor.py`:
```python
"""F-6: LiveExitExecutor — real market flatten, guard-blocked."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from shared.execution.live_exit_executor import LiveExitExecutor
from shared.execution.passive_maker import Fill


@pytest.mark.asyncio
async def test_flatten_places_market_order_when_not_suspended():
    kis = AsyncMock()
    kis.place_futures_order.return_value = "EXIT-1"
    kis.await_fill.return_value = Fill(
        order_id="EXIT-1", price=329.5, quantity=1, filled_at_ms=2000
    )
    guard = AsyncMock()
    guard.is_live_suspended.return_value = False
    ex = LiveExitExecutor(kis_client=kis, live_mode_guard=guard, redis=AsyncMock())
    fill = await ex.flatten(
        symbol="A05603", side="short", quantity=1, requested_price=330.0, now_ms=2000
    )
    assert fill is not None and fill.price == 329.5
    assert kis.place_futures_order.await_args.kwargs["order_type"] == "market"
    assert kis.place_futures_order.await_args.kwargs["side"] == "short"
    assert kis.place_futures_order.await_args.kwargs["price"] is None


@pytest.mark.asyncio
async def test_flatten_blocked_when_suspended_places_no_order():
    kis = AsyncMock()
    guard = AsyncMock()
    guard.is_live_suspended.return_value = True
    ex = LiveExitExecutor(kis_client=kis, live_mode_guard=guard, redis=AsyncMock())
    fill = await ex.flatten(
        symbol="A05603", side="short", quantity=1, requested_price=330.0, now_ms=2000
    )
    assert fill is None
    kis.place_futures_order.assert_not_awaited()  # guard-blocked → no real order


@pytest.mark.asyncio
async def test_flatten_returns_none_when_unfilled():
    kis = AsyncMock()
    kis.place_futures_order.return_value = "EXIT-1"
    kis.await_fill.return_value = None  # not filled within timeout
    guard = AsyncMock()
    guard.is_live_suspended.return_value = False
    ex = LiveExitExecutor(kis_client=kis, live_mode_guard=guard, redis=AsyncMock())
    fill = await ex.flatten(
        symbol="A05603", side="short", quantity=1, requested_price=330.0, now_ms=2000
    )
    assert fill is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /tmp/f6-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/execution/test_live_exit_executor.py -q`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

Create `shared/execution/live_exit_executor.py`:
```python
"""Live exit executor for the decoupled futures order_router (F-6).

On a PseudoOCO stop/target/expiry trigger, place a REAL market order to flatten
the position via the KIS adapter. Guard-blocked: when live trading is suspended
(``futures:live:suspended`` or ``futures_live.enabled=false``) the exit is NOT
placed and ``flatten`` returns ``None`` so PseudoOCO keeps the handle active for
the next poll. (Operator-accepted trade-off: no auto-flatten while suspended —
emergency flatten is the kill_switch daemon's job. See the F-6 design doc §3.4.)
"""

from __future__ import annotations

import logging
from typing import Any

from shared.execution.passive_maker import Fill

logger = logging.getLogger(__name__)

# Market exits should fill near-immediately; this bounds the await.
_EXIT_FILL_TIMEOUT_SECONDS = 5.0


class LiveExitExecutor:
    """Place real market flatten orders for triggered brackets (guard-blocked)."""

    def __init__(self, *, kis_client: Any, live_mode_guard: Any, redis: Any) -> None:
        self._kis = kis_client
        self._guard = live_mode_guard
        self._redis = redis

    async def flatten(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        requested_price: float,  # noqa: ARG002 — audit price; market order ignores it
        now_ms: int,  # noqa: ARG002 — part of the close-executor interface
    ) -> Fill | None:
        if self._guard is not None and await self._guard.is_live_suspended(self._redis):
            logger.warning(
                "live exit blocked (suspended) symbol=%s side=%s qty=%d",
                symbol,
                side,
                quantity,
            )
            return None
        order_id = await self._kis.place_futures_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type="market",
            price=None,
        )
        fill = await self._kis.await_fill(
            order_id, timeout_seconds=_EXIT_FILL_TIMEOUT_SECONDS
        )
        if fill is None:
            logger.error(
                "live exit order %s not filled within %.1fs symbol=%s",
                order_id,
                _EXIT_FILL_TIMEOUT_SECONDS,
                symbol,
            )
        return fill
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /tmp/f6-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/execution/test_live_exit_executor.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire the live branch in `_build_and_run`**

Add to the local imports inside `_build_and_run`:
```python
    from shared.execution.live_exit_executor import LiveExitExecutor
```
In the `else:  # live` branch, replace the Task-2 placeholder lines:
```python
        exit_runtime_state = None
        exit_close_executor = None
        exit_feed = None
```
with:
```python
        exit_runtime_state = RuntimeRiskState(redis=redis_client, asset_class="futures")
        exit_close_executor = LiveExitExecutor(
            kis_client=kis_adapter, live_mode_guard=live_guard, redis=redis_client
        )
        exit_feed = futures_feed
```

- [ ] **Step 6: Verify + format + commit**

```bash
cd /tmp/f6-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/execution/test_live_exit_executor.py tests/unit/services/test_order_router_main.py -q
/home/deploy/project/kis_unified_sts/.venv/bin/black shared/execution/live_exit_executor.py services/order_router/main.py tests/unit/execution/test_live_exit_executor.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix shared/execution/live_exit_executor.py services/order_router/main.py tests/unit/execution/test_live_exit_executor.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/execution/live_exit_executor.py
git add shared/execution/live_exit_executor.py services/order_router/main.py tests/unit/execution/test_live_exit_executor.py
git commit -m "feat(f-6): LiveExitExecutor (real market flatten, guard-blocked) + live wiring"
```

---

## Task 4: integration test + full gate + PR

**Files:**
- Modify: `tests/integration/test_signal_to_fill_e2e.py`

- [ ] **Step 1: Add a paper exit-lifecycle integration test**

Append to `tests/integration/test_signal_to_fill_e2e.py` a test that drives one entry through to a simulated exit (reuse the file's existing fixtures/imports; add `from shared.execution.pseudo_oco import PseudoOCO`, `from unittest.mock import AsyncMock` if absent):
```python
@pytest.mark.asyncio
async def test_paper_entry_then_stop_exit_logs_two_fills():
    redis = fakeredis.aioredis.FakeRedis()
    fill_logger = FillLogger(redis=redis, stream=ORDER_FILL, batch_size=1)
    runtime_state = AsyncMock()
    pseudo_oco = PseudoOCO(
        fill_logger=fill_logger, runtime_state=runtime_state,
        multiplier_krw_per_point=50_000,
    )
    # entry filled long @ 331.20, stop 330.00
    await pseudo_oco.register_bracket(
        signal=_signal("long"), signal_id="s1",
        fill=Fill(order_id="E1", price=331.20, quantity=1, filled_at_ms=1000),
    )
    # market drops to 329 → stop fires (synthetic close @ stop 330.00)
    fired = await pseudo_oco.on_tick(symbol="A05603", price=329.0, now_ms=2000)
    assert len(fired) == 1
    fills = await redis.xrange(ORDER_FILL)
    roles = [f[1][b"trade_role"].decode() for f in fills]
    assert "stop_loss" in roles
    runtime_state.record_trade.assert_awaited_once()
```
(If `_signal`/`Fill`/`FillLogger`/`ORDER_FILL` aren't already imported in this file, add them — `ORDER_FILL = "order.fill.futures"` already exists from F-1.)

- [ ] **Step 2: Targeted + regression**

```bash
cd /tmp/f6-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/integration/test_signal_to_fill_e2e.py tests/unit/execution/ tests/unit/services/test_order_router_main.py -q
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -k "pseudo_oco or order_router or live_exit or signal_to_fill or runtime_state" -q
```
Expected: all PASS.

- [ ] **Step 3: Full gate (CI parity) + mypy**

```bash
cd /tmp/f6-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance -p no:randomly 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -15
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -8
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/execution/pseudo_oco.py shared/execution/live_exit_executor.py
```
Expected: green; mypy clean on the new/changed `shared/` files. (A local xdist flake on an unrelated `ConfigLoader`-singleton test is a known pre-existing env artifact — confirm any failure is NOT in a pseudo_oco/order_router/live_exit/runtime_state test; CI is the merge gate.)

- [ ] **Step 4: Commit + push + PR**

```bash
cd /tmp/f6-impl
git add tests/integration/test_signal_to_fill_e2e.py
git commit -m "test(f-6): e2e paper entry→stop-exit lifecycle"
git push -u origin feat/futures-exit-execution-f6
gh pr create --base main --head feat/futures-exit-execution-f6 \
  --title "feat(f-6): decoupled futures exit execution (paper simulated + live market, guard-blocked)" \
  --body "$(cat <<'EOF'
## What
Make the decoupled futures chain actually CLOSE positions. Previously order_router registered a
PseudoOCO bracket on fill but **nothing ever drove `on_tick`/`check_expiry`** (verified: called only
from tests) — so positions never closed. F-6 adds an order_router exit-monitor poll task that drives
the brackets, plus a pluggable close action:
- **paper:** simulated fill at the trigger price → `order.fill.futures.shadow` + PnL to `risk:state:futures:shadow`.
- **live:** real **market** exit order (opposite side, flatten) via the KIS executor → `order.fill.futures` + PnL to `risk:state:futures`.

## Why
The decoupled chain (post F-1/F-3) could enter but not exit — entries filled and brackets were
recorded-but-never-executed. This is the prerequisite for F-5 (futures monitor needs real
open→close lifecycles) and completes the F-1 shadow risk-state design (F-6 is its first writer).

## Design
- **Detection (both modes):** exit-monitor polls `KISFuturesPriceFeed.get_current_price` every
  `exit_poll_interval`s and drives `PseudoOCO.on_tick` (stop/target, loss-wins) + `check_expiry`
  (TTL). Event-loop-only poll (the feed's WS callback is sync/cross-thread). KIS server-side OCO is
  restricted → client-side detection in both modes.
- **Close action (pluggable):** `PseudoOCO` gains an optional `close_executor` (None=paper synthetic
  fill; set=live real order), `runtime_state`, and `multiplier_krw_per_point`. `OCOHandle` carries
  `entry_price`; PnL = (exit−entry)·sign·qty·multiplier → `record_trade` + `record_win/loss`.
- **Live exit = MARKET, guard-blocked:** `LiveExitExecutor.flatten` checks `LiveModeGuard`; if
  suspended/not-enabled it places **no** order and returns None → PseudoOCO keeps the handle ACTIVE
  for retry. **Documented trade-off:** no auto-flatten while suspended (emergency flatten = kill_switch
  daemon / orchestrator / manual). The decoupled live path is Phase-5-gated and not yet active, so
  today's practical risk is nil; this is the conservative "unproven exit-monitor places no orders
  while suspended" stance.

## Safety / back-compat
Paper places no real order structurally (close_executor=None). Default `PseudoOCO(...)` (no
runtime_state/close_executor) is behavior-identical → existing callers/tests unaffected. off mode
runs no exit-monitor. Loop is resilient (per-iteration try/except) and cancelled cleanly on shutdown.
Risk isolation preserved: paper→`risk:state:futures:shadow`, live→`risk:state:futures`.

## How tested
PseudoOCO PnL (long/short × win/loss, sign-correct) + close_executor (real-fill price, guard-blocked
keeps handle active) + back-compat; order_router exit-monitor (closes a bracket on price cross,
records PnL; no-feed→no monitor); LiveExitExecutor (market order when clear, no order when suspended,
None when unfilled); e2e paper entry→stop-exit lifecycle. Full gate green; mypy/ruff/black clean.

Spec: `docs/superpowers/specs/2026-06-07-futures-exit-execution-f6-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-07-futures-exit-execution-f6.md`

## Follow-ups
F-5 (futures monitor — consumes these exit fills), F-4 (MarketContext builder unification), F-8/F-9
cutover. Full live reconciliation (log_fill-after-real-order failure) is a Phase-5/F-9 concern.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §4.1 OCOHandle.entry_price → Task 1. ✓
- §4.2 PseudoOCO pluggable close + PnL (return bool, _record_pnl, del-on-close) → Task 1. ✓
- §4.3 LiveExitExecutor (market, guard-blocked, opposite side) → Task 3. ✓
- §4.4 order_router exit-monitor (on_startup/on_shutdown/_exit_monitor_loop, poll interval) → Task 2. ✓
- §4.5 per-mode wiring (paper shadow risk + no executor; live live-risk + LiveExitExecutor; feed passed both) → Task 2 (paper) + Task 3 (live). ✓
- §6 safety (paper no real order; guard-blocked retry; off no monitor; loop resilient; risk isolation) → Tasks 1-3 + tests. ✓
- §7 testing → Tasks 1-4. ✓
- §10 acceptance → Tasks 1-4. ✓

**Placeholder scan:** none — complete code in every step.

**Type consistency:** `PseudoOCO(*, fill_logger, venue, runtime_state=None, multiplier_krw_per_point=0.0, close_executor=None)`; `_close(...) -> bool`; close-executor interface `flatten(*, symbol, side, quantity, requested_price, now_ms) -> Fill | None` (matches `LiveExitExecutor.flatten` and the AsyncMock in PseudoOCO tests); `OrderRouterDaemon(..., futures_price_feed=None, exit_poll_interval=1.0)`; `_exit_monitor_loop` uses `datetime.now(UTC)` (imported) + `pseudo_oco.on_tick`/`check_expiry` (existing signatures). `RuntimeRiskState(redis=, asset_class="futures", key_suffix=...)` (F-1). PnL sign: long=+1, short=−1. Paper `filled_price` == trigger price (back-compat); live `filled_price` == real fill price.

**Open questions resolved:** exit-monitor = poll task (not cross-thread callback); paper synthetic vs live real via injected close_executor; live = market + guard-blocked (handle stays active on block); risk key by mode; exit_poll_interval default 1.0 (no config-schema change); LiveExitExecutor reuses the existing KISFuturesAdapter surface.
