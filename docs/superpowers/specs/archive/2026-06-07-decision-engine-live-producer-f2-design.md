# decision_engine Live Producer (F-2) — Design

**Status:** Approved (design) — 2026-06-07
**Scope unit:** F-2 of the futures-decoupling roadmap (Phase A producer). Depends on F-1 (mode-coherent stream naming). After this, the decoupled futures chain can produce real candidates in BOTH shadow and live modes.

---

## 1. Problem

`services/decision_engine/main.py::_build_and_run` builds a real `FuturesContextProvider` (→ runs Setup A/C → emits candidate signals) **only in `shadow` mode**. The `live` (and `off`) path uses an inert stub that returns `None`, so a `live` decision_engine emits nothing:

```python
if mode == "shadow":
    context_provider, feed, sync_redis = await _build_shadow_context_provider(redis_client)
else:                                  # off AND live → inert stub
    async def _stub_context_provider() -> None: return None
    context_provider = _stub_context_provider
```

This was shadow-first incrementalism. The builder itself (`_build_shadow_context_provider`) is **mode-agnostic** — it wires the real `raw_data` feed + `StreamingIndicatorEngine` + `FuturesDailyReference` + macro + scheduled-events, with nothing shadow-specific. F-1 already makes the candidate stream mode-correct (`_candidate_stream_for(mode)` → `signal.candidate.futures.shadow` for shadow, `signal.candidate.futures` for live). So the only thing missing for a live producer is letting `live` use the real builder.

## 2. Goal

Make `FUTURES_STRATEGY_DAEMON=live` produce real candidate signals to `signal.candidate.futures` (the live stream), using the same real context provider as shadow. `off`/unset stays inert. Nothing is enabled by default — `live` is an explicit operator env step.

## 3. Approach (decided)

Generalize the shadow-only producer wiring to all "producing" modes (shadow + live). Rename the mode-agnostic builder, add a `_is_producing_mode` predicate + a `_resolve_context_provider` selector so the mode→provider wiring is unit-testable without heavy I/O.

**Safety:** the live producer is **ungated** — it emits candidate signals to a stream, not orders. This matches `stock_strategy` and the established guard-at-order-layer principle: `LiveModeGuard` gates `order_router` (the wallet-authority stage); `risk_filter`/`order_router` are independently gated. A live decision_engine producing candidates while the chain is suspended is harmless (a suspended/paper/off `order_router` simply won't act on them). F-2 enables nothing by default.

## 4. Design

### 4.1 `_is_producing_mode`

```python
def _is_producing_mode(mode: str) -> bool:
    """True when the daemon should build a REAL context provider (shadow|live).

    off / unset / unknown → False → inert stub (no candidates emitted).
    """
    return mode in ("shadow", "live")
```

### 4.2 Rename `_build_shadow_context_provider` → `_build_context_provider`

Mechanically rename (only one internal call site; no test imports it). Generalize:
- The guard `if not symbol: raise RuntimeError("FUTURES_STRATEGY_SYMBOL must be set for shadow mode")` → `"... for shadow/live mode"`.
- Docstring: "Wire ... for a producing (shadow|live) decision_engine."
The body is unchanged (it was already mode-agnostic).

### 4.3 `_resolve_context_provider` selector

```python
async def _resolve_context_provider(mode: str, redis_client: Any) -> tuple[Any, Any, Any]:
    """Return (context_provider, feed, sync_redis) for the mode.

    Producing modes (shadow|live) → real FuturesContextProvider (+ feed +
    sync_redis to close on shutdown). Otherwise an inert stub returning None,
    with feed=sync_redis=None.
    """
    if _is_producing_mode(mode):
        return await _build_context_provider(redis_client)

    async def _stub_context_provider() -> None:
        return None

    return _stub_context_provider, None, None
```

### 4.4 `_build_and_run` wiring

Replace the inline `if mode == "shadow": ... else: stub` block with:
```python
    context_provider, feed, sync_redis = await _resolve_context_provider(mode, redis_client)
```
Everything else (setups, `candidate_stream = _candidate_stream_for(mode)`, daemon construction, the `finally` that stops `feed`/closes `sync_redis` when not None) is unchanged. Update the `_build_and_run` docstring to document the `live` mode (real provider → `signal.candidate.futures`).

## 5. Data flow

```
FUTURES_STRATEGY_DAEMON=live:
  raw_data ticks → StreamConsumerFeed → StreamingIndicatorEngine
    → FuturesContextProvider (real MarketContext)
    → Setup A/C → DecisionEngineDaemon
    → xadd signal.candidate.futures   (LIVE stream; consumed by risk_filter live)

FUTURES_STRATEGY_DAEMON=shadow:  (unchanged) → signal.candidate.futures.shadow
off / unset:                     inert stub → nothing emitted.
```

## 6. Error handling / safety

- **Ungated production** (§3): live emits candidates only; no orders. The wallet-authority stage (`order_router`) stays the gated one. Suspended/off order_router → candidates are simply not acted upon.
- **off / unknown → inert:** `_is_producing_mode` returns False for anything but shadow/live → stub → no candidates, no feed built.
- **No default enablement:** requires `FUTURES_STRATEGY_DAEMON=live` + `FUTURES_STRATEGY_SYMBOL` (the builder raises a clear error if the symbol is unset, in shadow OR live).
- **Resource cleanup unchanged:** the `finally` already closes `feed`/`sync_redis` when present (None in off mode).
- **No behavior change for shadow or off.**

## 7. Testing

- **`_is_producing_mode`** (`tests/unit/decision_engine/test_shadow_wiring.py`): off=False, shadow=True, live=True, unknown=False.
- **`_resolve_context_provider`** (new unit test): off → stub provider returns None + feed/sync None (no builder call); live → invokes `_build_context_provider` (monkeypatched to a sentinel) and returns its tuple; shadow → same as live (producing).
- **Integration** (`tests/integration/test_futures_strategy_daemon_shadow.py`): parametrize (or add a sibling) so the daemon+provider produce a candidate to BOTH `signal.candidate.futures.shadow` AND `signal.candidate.futures` — proving the live stream carries candidates end-to-end.
- **Regression:** existing decision_engine unit + shadow integration tests stay green (rename is internal; shadow behavior unchanged).
- Full CI-parity gate; mypy on `services/decision_engine/main.py`; ruff/black.

## 8. Out of scope

- Enabling the live chain (systemd `Environment=FUTURES_STRATEGY_DAEMON=live` — operator step).
- Any change to risk_filter/order_router gating (already correct from F-1/F-3/F-6).
- F-8 (systemd reconciliation + `FUTURES_ORCHESTRATOR_ENABLED` guard) / F-9 (cutover runbook) — Phase C, Gate-gated.
- A real VWAP/spread for the feed (F-4 out-of-scope note; not needed for A/C).

## 9. Risks / open items

- **Live producer + dormant chain:** if an operator sets `FUTURES_STRATEGY_DAEMON=live` but leaves `order_router` off/paper, candidates flow to `signal.candidate.futures` and are consumed by a live risk_filter (if running) but never become orders (order_router gates). This is the intended strangler state; documented. The full live chain still requires `order_router=live` + `futures_live.enabled` + un-suspended (Phase-5 Gate).
- **decision_engine `_resolve_mode` is non-canonicalizing** (returns the raw lowercased value). An unknown value → `_is_producing_mode` False → inert; `_candidate_stream_for` → live name (irrelevant when inert). Acceptable; no change needed.

## 10. Acceptance criteria

1. `FUTURES_STRATEGY_DAEMON=live` builds the real `FuturesContextProvider` (not the stub) and the daemon publishes candidates to `signal.candidate.futures`.
2. `shadow` and `off` behavior unchanged (shadow → real provider → `.shadow`; off → inert).
3. `_is_producing_mode` + `_resolve_context_provider` are unit-tested; the live integration path is covered.
4. The producer is ungated (no `futures_live`/suspended check in decision_engine); enabling is an explicit env step.
5. Existing tests green; full gate green; mypy/ruff/black clean.
