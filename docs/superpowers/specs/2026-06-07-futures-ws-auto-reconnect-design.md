# Futures WS Auto-Reconnect — Design

**Date:** 2026-06-07
**Status:** Approved (Increment 2 of paper-readiness; operator opted in via "Include the futures reconnect fix")
**Scope:** Single subsystem — `shared/kis/futures_feed.py` (`KISFuturesPriceFeed`).

---

## Problem

The stock price feed (`KISStockPriceFeed`) auto-reconnects when its WebSocket
drops: `_on_close` (while `_running`) spawns a `_reconnect()` thread that retries
with exponential backoff, re-subscribes all symbols, and records
`record_ws_reconnect("stock")`.

The **futures** price feed has **no such recovery**. `KISFuturesPriceFeed.start()`
spawns a single thread running `self._adapter.subscribe(symbols, on_tick)`. That
call blocks inside the adapter's `while self.is_running:` queue-drain loop. When
the underlying WebSocket drops:

1. `KISWebSocketAdapter._run_websocket`'s `run_forever()` returns,
2. its `finally` sets `is_running = False` (and `is_connected = False`),
3. `subscribe()`'s `while self.is_running:` loop exits and the thread ends.

The feed is now **permanently dead** — `_running` is still `True`, but no thread
is reading ticks, `get_staleness_seconds()` climbs forever, and the only recovery
is a full process restart. For tomorrow's stock+futures paper run this is a silent
single-point failure on the futures data path.

The disconnect itself **is** already observable: `KISWebSocketAdapter._on_close`
records `record_ws_disconnect("futures")` (added in #432). What's missing is the
**recovery** and its `record_ws_reconnect("futures")` counterpart.

---

## Goal

Bring the futures feed to parity with the stock feed: automatically reconnect
after an unexpected WS drop, with exponential backoff, re-subscription, and a
best-effort `record_ws_reconnect("futures")` metric — while leaving a deliberate
`stop()` clean (no reconnect storm) and keeping the change confined to the futures
feed wrapper.

---

## Locus decision: the wrapper, not the shared adapter

Reconnect logic lives in **`KISFuturesPriceFeed` (`shared/kis/futures_feed.py`)**,
**not** in the shared `KISWebSocketAdapter` (`shared/kis/websocket.py`).

Rationale:

- **Smallest blast radius.** `KISWebSocketAdapter` is a generic adapter with its
  own test contract (`tests/unit/kis/`); the futures feed is its only runtime
  consumer for this path. Changing the adapter risks unrelated callers and a
  larger test surface.
- **Mirrors the proven stock pattern.** `KISStockPriceFeed` owns its reconnect in
  the *feed* layer. Putting the futures reconnect in the futures feed keeps the
  two feeds structurally analogous and easy to reason about side-by-side.
- **The adapter is single-shot by design.** After a drop, an adapter instance is
  spent (`is_running` is permanently `False`, its `_ws_thread` is dead). Rather
  than mutate the adapter to make itself restartable (invasive), the feed simply
  **creates a fresh adapter per reconnect attempt** — clean lifecycle, no stale
  state.

---

## Mechanism

### Supervisor thread

`start()` changes the worker thread's target from `self._adapter.subscribe` to a
new private supervisor method `_run_with_reconnect()`. The supervisor:

1. Runs the **initial** `self._adapter.subscribe(self._symbols, self._on_tick)`
   (the adapter is already `connect()`-ed by `start()`). This blocks until the WS
   drops or `stop()` is called.
2. Enters the reconnect loop:

```
delay = self._reconnect_initial_delay
while self._running:
    time.sleep(delay)
    if not self._running:
        break
    try:
        # Old adapter is spent (is_running permanently False); use a fresh one.
        self._adapter = KISWebSocketAdapter(self._config)
        self._adapter.connect()
        logger.info("[FuturesPriceFeed] Reconnected to futures WS feed")
        _record_ws_reconnect("futures")          # best-effort
        delay = self._reconnect_initial_delay    # reset backoff on success
        self._adapter.subscribe(self._symbols, self._on_tick)  # blocks until next drop
        # subscribe() returned: WS dropped again (or stop()). Loop re-checks _running.
    except Exception as e:
        logger.error("[FuturesPriceFeed] Reconnect attempt failed: %s", e)
        delay = min(delay * 2, self._reconnect_max_delay)  # backoff on failure
```

This exactly mirrors `stock_feed._reconnect`'s shape: pre-sleep, post-sleep
`_running` re-check, reset-on-success, `min(delay*2, max)`-on-failure.

### Stop distinction (no reconnect on deliberate stop)

`stop()` is unchanged in ordering and already correct:

```
self._running = False          # set FIRST
self._adapter.disconnect()     # ends the current subscribe() loop
self._thread.join(timeout=...)
```

Because `_running` is set to `False` *before* `disconnect()`, when the current
`subscribe()` returns the supervisor's `while self._running:` is already `False`
→ no reconnect. If the supervisor happens to be mid-`time.sleep(delay)` during
backoff, the post-sleep `if not self._running: break` exits cleanly. This is the
same guarantee the stock feed relies on (`_on_close` checks `if self._running:`).

The supervisor thread is a `daemon` thread (as today), so a worst-case in-flight
`sleep(delay)` up to `reconnect_max_delay` cannot block process exit. `stop()`'s
`join(timeout=self._shutdown_timeout)` is best-effort, matching current behavior
and the stock feed.

### Adapter reassignment safety

`self._adapter` is reassigned in the supervisor thread and read in `stop()` /
`get_health_status()` from the main thread. Attribute assignment is atomic under
the GIL, and every value read is always a fully-constructed adapter (old or new) —
no torn reads, no lock needed. This matches how the stock feed reassigns
`self._ws` without a lock.

---

## Config

Add two knobs to `config/streaming.yaml::futures_feed`, mirroring `stock_feed`:

```yaml
futures_feed:
  ...
  reconnect_initial_delay: 1.0   # 재접속 초기 대기 (초)
  reconnect_max_delay: 60.0      # 재접속 최대 대기 (초)
```

Read in `KISFuturesPriceFeed.__init__` via `feed_cfg.get(key, default)` so an
older config without these keys still loads (back-compat):

```python
self._reconnect_initial_delay = float(feed_cfg.get("reconnect_initial_delay", 1.0))
self._reconnect_max_delay = float(feed_cfg.get("reconnect_max_delay", 60.0))
```

---

## Metric

The `record_ws_reconnect` collector method already exists (added in #432). Add a
module-level best-effort helper in `futures_feed.py`, mirroring the existing
`websocket._record_ws_disconnect`:

```python
def _record_ws_reconnect(feed: str) -> None:
    """Best-effort WS reconnect counter (never breaks the WS thread)."""
    try:
        from services.monitoring.metrics import get_metrics_collector
        get_metrics_collector().record_ws_reconnect(feed)
    except Exception:  # noqa: BLE001 — observability must never break the WS thread
        pass
```

The existing `_record_ws_disconnect("futures")` at `shared/kis/websocket.py:630`
is **preserved** — disconnect is recorded by the adapter, reconnect by the feed,
giving a matched disconnect/reconnect counter pair on `feed="futures"`.

---

## Real-money safety

- The reconnect path re-establishes **only the read-only price feed** (orderbook +
  trade ticks). It places **no orders** and mutates **no positions** — order
  placement lives entirely in the order_router / executor, untouched here.
- A **fresh adapter per attempt** prevents thread leaks and double-reconnect: there
  is exactly one supervisor thread, and a spent adapter is never resubscribed.
- Backoff is bounded (`reconnect_max_delay`), so a prolonged outage cannot busy-spin
  the API or trip the KIS rate limiter.

---

## Testing strategy

New tests in `tests/unit/kis/test_futures_feed_reconnect.py`, using the
unbound-method + fake-self (`SimpleNamespace`) pattern where convenient and the
real `KISFuturesPriceFeed` where construction is cheap:

1. **Metric helper** — `_record_ws_reconnect("futures")` calls the collector;
   swallows collector construction failure and method failure (no raise).
2. **Config knobs** — `__init__` reads `reconnect_initial_delay` /
   `reconnect_max_delay` from `futures_feed`, and falls back to `1.0` / `60.0`
   when absent.
3. **No reconnect after stop** — with `_running = False`, the supervisor loop does
   not attempt a reconnect (no fresh adapter created, `connect` not called).
4. **Backoff on drop** — patch `subscribe` to return immediately and `connect` to
   succeed, patch `time.sleep`, and flip `_running = False` after N iterations;
   assert a fresh adapter was constructed, `connect()` called, and
   `record_ws_reconnect("futures")` recorded; assert backoff resets on success.
5. **Backoff escalation on connect failure** — `connect` raises; assert
   `delay` grows by `min(delay*2, max)` and the loop retries while `_running`.

The full pytest gate (`test` job) is the real merge gate; lint/type-check are
advisory (continue-on-error).

---

## Out of scope

- No change to `KISWebSocketAdapter` reconnect behavior (it stays single-shot).
- No change to the stock feed.
- No change to `update_symbols`-while-running semantics (still unsupported; the
  supervisor re-subscribes the symbol set captured at `start()`).
