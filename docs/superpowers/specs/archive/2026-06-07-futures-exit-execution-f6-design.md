# Futures Decoupled Exit Execution (F-6) — Design

**Status:** Approved (design) — 2026-06-07
**Scope unit:** F-6 of the futures-decoupling roadmap (Phase B). Depends on F-1 (`RuntimeRiskState.key_suffix`, stream naming) and F-3 (order_router paper/live modes). Precedes F-5 (futures monitor needs real open→close lifecycles).

---

## 1. Problem

The decoupled futures chain **cannot close a position.** On a filled entry, `order_router` calls `PseudoOCO.register_bracket(...)` (`services/order_router/main.py:277-282`), but **nothing ever drives `PseudoOCO.on_tick`/`check_expiry`** — verified: those methods are called only from `tests/unit/execution/test_pseudo_oco.py`, never from `services/`, and the order_router `StreamStage.run()` loop only pumps the final-signal stream (no secondary price loop, no `set_tick_callback`). So an entry fills, a stop+target bracket is *recorded*, and the position stays open forever. There is no exit path.

Additionally, `PseudoOCO` is **fill-logger-only**: `_close` (`pseudo_oco.py:183-217`) logs a synthetic exit fill via `FillLogger` but never places a real order and never records risk state. That is correct for a *paper* close, but it means a live decoupled position could never be flattened by this component either.

## 2. Goal

Make the decoupled chain actually exit positions, in **both** modes:
- **Paper (`FUTURES_ORDER_ROUTER=paper`):** drive the brackets so they fire; closes are **simulated** fills at the trigger price, logged to `order.fill.futures.shadow`, with realized PnL recorded to the shadow risk state `risk:state:futures:shadow`.
- **Live (`FUTURES_ORDER_ROUTER=live`):** on a trigger, place a **real market exit order** (opposite side, flatten qty) via the live KIS executor, await the real fill, log it to `order.fill.futures`, and record PnL to the live `risk:state:futures`.

This makes F-6 the **first decoupled-chain writer of futures risk state**, completing the F-1 `key_suffix` isolation design. It also gives F-5 (futures monitor) real open→close lifecycles to bridge.

## 3. Approach (decided)

1. **Drive the existing PseudoOCO** rather than build a separate exit daemon — PseudoOCO already implements stop/target (loss-wins) + TTL detection. KIS server-side OCO is restricted, so trigger **detection is client-side in both modes**.
2. **Periodic poll task** (event-loop-only) on order_router, not the feed's cross-thread WS callback. `set_tick_callback` is a *sync* callback invoked from the feed's WS *thread* (`shared/kis/futures_feed.py:367`), so driving the async `on_tick` from it would require `run_coroutine_threadsafe` (fragile). Instead a single asyncio task polls `feed.get_current_price(symbol)` every `exit_poll_interval`s and drives `on_tick` + `check_expiry` — mirrors `stock_exit`'s decision-cadence timer loop.
3. **Pluggable close action.** PseudoOCO gets an optional injected close-executor: absent (paper) → synthesize a fill at the trigger price (current behavior); present (live) → place a real market order and use the real fill.
4. **Live exit = market order, guard-blocked.** Triggered live exits place a MARKET order (guarantee flatten) and ARE subject to `LiveModeGuard` (`futures_live.enabled` + `futures:live:suspended`). If blocked, the close is skipped and the handle stays ACTIVE (retried next poll). **Implication (documented, operator-accepted):** when live is suspended, this monitor will NOT auto-flatten real positions — emergency flattening relies on the kill_switch daemon / orchestrator / manual action. The decoupled live path is Phase-5-gated and not yet active, so today's practical risk is nil; this is the conservative "an unproven exit-monitor places no orders while suspended" stance.
5. **Shadow risk isolation.** Paper records to `risk:state:futures:shadow` (F-1 `key_suffix="shadow"`); live to `risk:state:futures`.

## 4. Design

### 4.1 `OCOHandle` gains entry price + closed price

`OCOHandle` (`shared/execution/pseudo_oco.py:40-52`) adds `entry_price: float = 0.0`. `register_bracket` already receives the entry `fill` (`pseudo_oco.py:85`) → set `entry_price=fill.price`. This is needed for PnL = `(exit_price − entry_price) · sign · qty · multiplier`.

### 4.2 `PseudoOCO` — pluggable close + PnL recording

Constructor gains three optional, backward-compatible params:
```python
def __init__(
    self,
    *,
    fill_logger: FillLogger,
    venue: str = "KRX",
    runtime_state: "RuntimeRiskState | None" = None,
    multiplier_krw_per_point: float = 0.0,
    close_executor: "ExitCloseExecutor | None" = None,
) -> None:
```
- `runtime_state` — when set, realized PnL is recorded on each close.
- `multiplier_krw_per_point` — contract multiplier for PnL (futures = 50_000; from `ContractSpec`).
- `close_executor` — when set (live), `_close` places a real order through it; when None (paper), `_close` synthesizes a fill at the trigger price (current behavior).

Default (`None`/`0.0`) reproduces today's behavior exactly → existing tests + any other caller unaffected.

`_close` is restructured to **return `bool`** (closed vs blocked) and to record PnL:
```python
async def _close(self, handle, *, fill_price, now_ms, trade_role, order_type, new_state) -> bool:
    if self._close_executor is not None:
        real_fill = await self._close_executor.flatten(
            symbol=handle.symbol,
            side=_opposite(handle.direction),
            quantity=handle.quantity,
            requested_price=fill_price,
            now_ms=now_ms,
        )
        if real_fill is None:
            # guard-blocked / not placeable → leave handle ACTIVE for retry
            return False
        actual_price = float(real_fill.price)
    else:
        actual_price = fill_price  # paper: synthetic fill at the trigger price
    handle.state = new_state
    await self.fill_logger.log_fill(... filled_price=actual_price ...)
    await self._record_pnl(handle, exit_price=actual_price)
    return True
```
`on_tick`/`check_expiry` only remove the handle when `_close` returns `True`; a blocked live close (`False`) keeps the handle ACTIVE for the next poll.

`_record_pnl`:
```python
async def _record_pnl(self, handle, *, exit_price) -> None:
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

### 4.3 `ExitCloseExecutor` (live) — real market flatten, guard-blocked

A small duck-typed interface (no new heavy class). The live implementation wraps the existing `KISFuturesAdapter` (already built in order_router's live branch, F-3) + the `LiveModeGuard`:
```python
class LiveExitExecutor:
    def __init__(self, *, kis_client, live_mode_guard, redis) -> None: ...
    async def flatten(self, *, symbol, side, quantity, requested_price, now_ms) -> Fill | None:
        # guard-blocked: if live suspended / not enabled → return None (skip, retry next poll)
        if self._guard is not None and await self._guard.is_live_suspended(self._redis):
            logger.warning("live exit blocked (suspended) symbol=%s side=%s", symbol, side)
            return None
        order_id = await self._kis.place_futures_order(
            symbol=symbol, side=side, quantity=quantity, order_type="market", price=None,
        )
        return await self._kis.await_fill(order_id, timeout_seconds=...)
```
- Uses `kis_client.place_futures_order(order_type="market", price=None)` + `await_fill` — the same `KISFuturesAdapter` surface F-3 defined. No new executor plumbing.
- Returns `None` when guard-blocked → PseudoOCO keeps the handle active.
- `side = _opposite(entry direction)` to flatten (long entry → SELL exit; short entry → BUY-to-cover).

Paper mode passes **no** close_executor (synthetic fills only — never a real order, structurally).

### 4.4 order_router exit-monitor poll task

`OrderRouterDaemon.__init__` gains optional: `futures_price_feed=None`, `exit_poll_interval: float = 1.0`, plus the `pseudo_oco` it already has (now carrying runtime_state/close_executor). The monitor runs only when `futures_price_feed` is wired (paper AND live; off → never).

- `on_startup` (extend existing): after the sentinel check, if `self.futures_price_feed is not None`, start `self._exit_task = asyncio.create_task(self._exit_monitor_loop())`.
- `on_shutdown` (new): cancel `self._exit_task` and await its cancellation.
- `_exit_monitor_loop`:
```python
async def _exit_monitor_loop(self) -> None:
    while not self._stop.is_set():
        try:
            price = await self.futures_price_feed.get_current_price(self.locked_symbol)
            close = price.get("close") if price else None
            now_ms = int(time.time() * 1000)
            if close is not None:
                await self.pseudo_oco.on_tick(symbol=self.locked_symbol, price=float(close), now_ms=now_ms)
            await self.pseudo_oco.check_expiry(now_ms=now_ms, market_price=float(close) if close is not None else None)
        except Exception:
            logger.exception("exit-monitor iteration failed; continuing")
        await asyncio.sleep(self.exit_poll_interval)
```
The loop never raises out (a bad iteration is logged + retried) so the consume loop and feed stay alive.

### 4.5 `_build_and_run` wiring (per mode)

- **off:** inert (existing early-return) — no feed, no monitor.
- **paper:** build `RuntimeRiskState(redis, asset_class="futures", key_suffix="shadow")`; build `PseudoOCO(fill_logger=…, runtime_state=…, multiplier_krw_per_point=spec.multiplier_krw_per_point, close_executor=None)`; pass `futures_price_feed=futures_feed` to the daemon. → simulated exits, shadow risk.
- **live:** build `RuntimeRiskState(redis, asset_class="futures", key_suffix="")`; build `LiveExitExecutor(kis_client=kis_adapter, live_mode_guard=live_guard, redis=redis_client)`; build `PseudoOCO(fill_logger=…, runtime_state=…, multiplier_krw_per_point=spec.multiplier_krw_per_point, close_executor=live_exit_executor)`; pass `futures_price_feed=futures_feed`. → real market exits (guard-blocked), live risk.

(The fill stream the closes are logged to is already mode-correct from F-1: FillLogger uses `order.fill.futures[.shadow]`.)

## 5. Data flow

```
PAPER (shadow pipeline):
  entry fill → register_bracket(entry_price) → [exit-monitor poll] get_current_price
    → on_tick: stop/target hit → _close (synthetic fill @ trigger) → log order.fill.futures.shadow
       → record_trade/loss/win → risk:state:futures:shadow
    → check_expiry: TTL → _close (force_close) → …

LIVE (Phase-5 gated):
  entry fill → register_bracket(entry_price) → [exit-monitor poll] get_current_price
    → on_tick: stop/target hit → _close → LiveExitExecutor.flatten:
         guard suspended? → None → handle stays ACTIVE (retry next poll)
         else → place MARKET order (opposite side) → await real fill
       → log order.fill.futures (real price) → record_trade/loss/win → risk:state:futures
```

## 6. Error handling / safety

- **Paper places no real order — structurally:** paper passes `close_executor=None`; `_close` only synthesizes a fill. No KIS order object is reachable.
- **Live exits are guard-blocked (operator-chosen):** when `futures:live:suspended` (or `futures_live.enabled=false`), `LiveExitExecutor.flatten` returns `None` → the handle stays ACTIVE and retries each poll → **no auto-flatten while suspended.** Documented trade-off (§3.4). Emergency flatten = kill_switch daemon / orchestrator / manual.
- **off → no monitor:** the exit-monitor only starts when a feed is wired; off mode never builds one.
- **Idempotency / double-fire:** `_close` sets `handle.state` only after a successful close (paper always; live on real fill), and `on_tick`/`check_expiry` delete the handle only on `True`. A blocked or failed live order leaves the handle ACTIVE — it will retry, not double-close. If `log_fill` fails *after* a real order placed (live), the real position is closed but unlogged → logged loudly as a reconciliation gap (mirrors the existing order_router error taxonomy; NO XACK semantics unchanged for the consume loop, which is independent of the monitor).
- **Loop resilience:** `_exit_monitor_loop` catches per-iteration exceptions and continues; it is cancelled cleanly on shutdown.
- **Risk-state isolation:** paper → `risk:state:futures:shadow`; live → `risk:state:futures`. A shadow run never moves live risk counters (F-1 guarantee preserved; this is its first writer).

## 7. Testing

- **PseudoOCO PnL + close (`tests/unit/execution/test_pseudo_oco.py`):** entry_price stored; `_close` returns True (paper) and records PnL to a fake `RuntimeRiskState` (long win, long loss, short win, short loss — sign correctness); `record_win`/`record_loss` per PnL sign; default (no runtime_state) records nothing (back-compat); existing tests still pass.
- **PseudoOCO with live close_executor:** `_close` calls `close_executor.flatten`; on `Fill` → logs at the real fill price + records PnL + removes handle; on `None` (blocked) → handle stays ACTIVE, no fill logged, no PnL.
- **order_router exit-monitor (`tests/unit/services/test_order_router_main.py` or new):** drive a daemon with a fake feed + a registered bracket; one poll where the price crosses the stop → exit fill logged + PnL recorded; expiry path; off/no-feed → no monitor task.
- **LiveExitExecutor:** guard-suspended → returns None, no order placed; guard-clear → places market order via mock adapter, returns the fill.
- **Integration (`tests/integration/test_signal_to_fill_e2e.py` extend or new):** full paper chain entry→bracket→simulated stop cross→exit fill on `order.fill.futures.shadow`.
- **Regression:** full CI-parity gate; mypy on changed `shared/` files; ruff/black.

## 8. Out of scope

- A separate `services/futures_exit/` daemon (PseudoOCO + the order_router monitor suffice).
- F-5 futures monitor (next increment; consumes the exit fills this produces).
- Changing the entry path, PassiveMaker, risk_filter, decision_engine, or the off-inert behavior.
- KIS server-side OCO (restricted; client-side detection is intentional).
- Auto-flatten while live is suspended (operator-chosen guard-blocked behavior; §3.4).

## 9. Risks / open items

- **Guard-blocked live exits leave positions open while suspended** — see §3.4/§6. Operator-accepted; mitigated by the (separate) kill_switch force-flatten path and the fact that the decoupled live path is not yet active.
- **Poll cadence latency:** exits fire at most every `exit_poll_interval`s (default 1s), not per tick. Acceptable for 1-minute-bar Setup A/C stop/target brackets (the orchestrator itself runs a ~1-minute cycle). Configurable.
- **Live `log_fill`-after-real-order failure** = reconciliation gap (§6) — logged loudly; full reconciliation is a Phase-5/F-9 concern.
- **PnL uses the trigger price in paper** (slippage 0) — faithful to the paper model; live uses the real fill price.

## 10. Acceptance criteria

1. The decoupled chain closes positions: a registered bracket fires via the order_router exit-monitor (paper: simulated fill; live: real market order).
2. Paper closes log to `order.fill.futures.shadow` and record PnL to `risk:state:futures:shadow`; live closes log to `order.fill.futures` and record to `risk:state:futures`.
3. Live exits are MARKET orders, guard-blocked (suspended → skipped + retried, handle stays ACTIVE); paper never places a real order.
4. `OCOHandle.entry_price` + PnL math (sign-correct long/short); `record_win`/`record_loss` per sign.
5. Default `PseudoOCO(...)` (no runtime_state/close_executor) is byte-for-byte behavior-compatible; existing callers/tests unaffected.
6. off mode runs no exit-monitor; the monitor loop is resilient (per-iteration try/except) and cancelled cleanly on shutdown.
7. Tests per §7; full gate green; mypy/ruff/black clean.
