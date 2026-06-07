# Futures Chain Stream-Naming Coherence (F-1) — Design

**Status:** Approved (design) — 2026-06-07
**Author:** decoupling working session
**Scope unit:** F-1 of the futures-decoupling roadmap (`futures-decoupling-state` memory). Prerequisite for any full-chain shadow run; precedes F-2 (decision_engine live producer).

---

## 1. Problem

The decoupled futures daemon chain — `services/decision_engine` → `services/risk_filter` → `services/order_router` (+ `services/kill_switch`) — cannot run end-to-end because its Redis stream names are **incoherent across producers and consumers** and have **no per-mode (shadow vs live) isolation**, unlike the already-coherent stock M4 chain.

Evidence (current `main`, post-F-3):

- **decision_engine** (`FUTURES_STRATEGY_DAEMON`, modes off/shadow/live): `_candidate_stream_for(mode)` returns `signal.candidate.futures.shadow` for shadow but the **legacy** `stream:signal.candidate` for off/live (`services/decision_engine/main.py:125-135`). Two unrelated base names.
- **risk_filter**: has **no mode helper at all** — hardcodes consume `stream:signal.candidate` (`main.py:189`) and produce `stream:signal.final` (`main.py:190`). In shadow the decision_engine writes `signal.candidate.futures.shadow`, which risk_filter never reads → **chain dead in shadow**.
- **order_router** (`FUTURES_ORDER_ROUTER`, off/paper/live from F-3): execution mode exists, but stream names are hardcoded — consume `stream:signal.final` (`main.py:415`), log fills to `stream:order.fill` (`main.py:368`). No `.shadow` form → a paper run cannot be isolated from a live run.
- Three different mode env vars (`FUTURES_STRATEGY_DAEMON`, `FUTURES_ORDER_ROUTER`, none) and inconsistent base-name conventions (`stream:signal.*` prefix on futures vs `signal.*.stock` infix on stock).

The stock chain solved this: each daemon has `_resolve_mode()` + a `_streams_for(mode)`-style helper, applies a `.shadow` suffix to stream names in shadow mode, uses bases `signal.{candidate,final}.stock` / `order.fill.stock`, and makes them env-overridable. `risk:state:{asset}` is deliberately never suffixed (shared across modes).

## 2. Goal

Make the futures chain **mode-coherent and shadow-isolatable**, mirroring the stock pattern, so a later increment can run a fully isolated futures shadow pipeline alongside (eventual) live without cross-talk. Two pipelines result:

- **Shadow pipeline** = decision_engine `shadow` + risk_filter `shadow` + order_router `paper`, entirely on `.shadow` streams, with isolated (non-live) risk state.
- **Live pipeline** = all three on unsuffixed streams, live risk state.
- `off` = inert everywhere (default).

**Non-goal:** *enabling* a shadow run (systemd env changes are an operator step), F-2 (decision_engine live producer), the shared-helper DRY extraction, and a futures monitor / dashboard `:shadow` wiring. See §8.

## 3. Approach (decided)

Two design forks were resolved with the operator:

1. **Clean mirror, per-module.** Adopt stock-style base names and a `.shadow` suffix; add per-daemon `_resolve_mode`/`_streams_for` helpers to the three futures daemons, mirroring stock's existing per-module style. Do **not** touch the working stock chain. Do **not** extract a shared helper yet (deferred DRY cleanup).
2. **Isolated streams + safe risk-state.** The shadow/paper path runs entirely on `.shadow` streams AND must not read or write the live `risk:state:futures` — a deliberate divergence from stock's shared-risk-state exemption, justified because futures is the real-money path and a shadow run must never trip the live kill_switch or move live risk counters.

## 4. Design

### 4.1 Stream base names

Drop the legacy `stream:` prefix; mirror stock exactly. (decision_engine's shadow form already uses the prefix-less `signal.candidate.futures.shadow`, so this only makes the live form consistent.)

| Logical stream | live form | shadow form |
|---|---|---|
| candidate (decision_engine → risk_filter) | `signal.candidate.futures` | `signal.candidate.futures.shadow` |
| final (risk_filter → order_router) | `signal.final.futures` | `signal.final.futures.shadow` |
| fill (order_router → FillLogger) | `order.fill.futures` | `order.fill.futures.shadow` |

Suffix convention (matches stock): **streams use `.shadow` (dot)**; **state keys use `:shadow` (colon)**.

### 4.2 Per-daemon mode → stream wiring

Each daemon keeps its existing env var; risk_filter gets a new one. Each gets a module-level `_resolve_mode()` (default `"off"`, `.strip().lower()`, canonicalized to the daemon's valid mode set) and a per-mode stream helper. All stream names remain env-overridable (mirroring stock's `STOCK_*_STREAM`), via `FUTURES_CANDIDATE_STREAM` / `FUTURES_FINAL_STREAM` / `FUTURES_FILL_STREAM`.

**decision_engine** — `FUTURES_STRATEGY_DAEMON` ∈ {off, shadow, live}:
- `_candidate_stream_for(mode)`: `shadow` → `signal.candidate.futures.shadow`; `live` → `signal.candidate.futures`; (off → inert, no publish — existing behavior).
- Only change vs today: the `live`/off branch returns `signal.candidate.futures` instead of `stream:signal.candidate`.

**risk_filter** — **new** `FUTURES_RISK_FILTER` ∈ {off, shadow, live}:
- Add `_resolve_mode()` + an off-inert gate (the daemon currently has neither).
- `_streams_for(mode) -> (candidate, final)`: `shadow` → (`signal.candidate.futures.shadow`, `signal.final.futures.shadow`); `live` → (`signal.candidate.futures`, `signal.final.futures`).
- Replace the hardcoded `candidate_stream`/`final_stream` (`main.py:189-190`) with the derived pair (env-overridable).
- Consumer group name `"risk_filter"` stays fixed (not mode-suffixed) — matches stock (`stock_risk_filter`).

**order_router** — `FUTURES_ORDER_ROUTER` ∈ {off, paper, live} (existing, F-3):
- Add `_final_stream_for(mode)` + `_fill_stream_for(mode)`: `paper` → (`signal.final.futures.shadow`, `order.fill.futures.shadow`); `live` → (`signal.final.futures`, `order.fill.futures`).
- Replace hardcoded `final_stream` (`main.py:415`) and FillLogger `stream` (`main.py:368`) with the derived values.
- `paper` consuming the `.shadow` final stream is what closes the isolated shadow pipeline (decision_engine shadow → risk_filter shadow → order_router paper). `off` stays inert (F-3). The execution paper/live split (PaperKISFuturesAdapter vs KISFuturesAdapter, guard) from F-3 is unchanged.

### 4.3 Safe risk-state (shadow isolation)

Current futures risk-state plumbing (verified):
- **Readers only** in the decoupled chain: `risk_filter` (`main.py:114` `snapshot()`) and `kill_switch` (`main.py:183` `snapshot()`), both via `RuntimeRiskState(redis=…, asset_class="futures")` → key `risk:state:futures` (+ `:meta`).
- **No writer** in the decoupled futures chain (the `RuntimeRiskState` writers are `stock_exit` for stock and the orchestrator path; a futures fill→risk writer is F-6, not yet built).
- **order_router paper mode is already risk-isolated**: the Gate-3 daily-trade counter INCR (`order_router:daily_trades:{kst-date}`) and every cap check sit behind `if guard is not None` (`OrderRouterDaemon`, `main.py:222`), and paper sets `guard_for_daemon = None` (F-3). Paper therefore writes neither the daily-trade counter nor any risk:state. **No change needed in order_router for risk isolation.**

So "safe risk-state" reduces to a single change: **risk_filter in shadow mode must read a suffixed `risk:state:futures:shadow` key** rather than the live one, so shadow filter decisions are isolated (the shadow key has no writer → empty → clean-slate risk state → an isolated shadow pipeline is not gated by live trading history).

Mechanism — add a backward-compatible `key_suffix` to `RuntimeRiskState`:
```python
def __init__(self, *, redis, asset_class="futures", key_suffix: str = "") -> None:
    self._redis = redis
    self._asset_class = asset_class
    suffix = f":{key_suffix}" if key_suffix else ""
    self._risk_state = RiskState(redis, asset_class, key=f"risk:state:{asset_class}{suffix}")
    self._meta_key = f"risk:state:{asset_class}{suffix}:meta"
```
- Default `key_suffix=""` → identical keys to today → **stock and all existing callers unaffected**.
- `risk_filter._build_and_run`: `key_suffix = "shadow" if mode == "shadow" else ""`, passed to `RuntimeRiskState`.
- `kill_switch`: unchanged — it is the **live** safety daemon and reads live `risk:state:futures`. The shadow pipeline runs without a kill_switch (out of scope; documented). Because the shadow chain never writes live risk state, the live kill_switch is unaffected by shadow activity.

This is a deliberate divergence from stock (whose `risk:state:stock` is shared across modes). Futures is real-money; the isolation is the point.

### 4.4 What stays the same

- `StreamStage` (`shared/streaming/stage.py`) — names are constructor args; no change.
- Consumer-group names (`risk_filter`, `order_router`) — fixed, not mode-suffixed (matches stock).
- order_router execution paper/live split, PassiveMaker, PseudoOCO, FillLogger, OrderRouterDaemon internals — unchanged (F-3).
- kill_switch sentinel/stream — global, mode-blind — unchanged.
- decision_engine `off`-inert stub and tick-feed input — unchanged.

## 5. Data flow

```
SHADOW (isolated):
  tick feed → decision_engine[FUTURES_STRATEGY_DAEMON=shadow]
            → xadd signal.candidate.futures.shadow
            → risk_filter[FUTURES_RISK_FILTER=shadow] (reads risk:state:futures:shadow)
            → xadd signal.final.futures.shadow
            → order_router[FUTURES_ORDER_ROUTER=paper] (PaperKISFuturesAdapter, guard=None)
            → FillLogger xadd order.fill.futures.shadow

LIVE (future, gated):
  tick feed → decision_engine[live] → signal.candidate.futures
            → risk_filter[live] (reads risk:state:futures)
            → signal.final.futures
            → order_router[live] (KISFuturesAdapter + LiveModeGuard)
            → order.fill.futures

OFF (default): every daemon inert.
```

## 6. Error handling / safety

- **Off-default everywhere** — an unset/empty/garbage env var resolves to `off` (canonicalized in `_resolve_mode`), so no daemon does anything until explicitly enabled. risk_filter gains the off-inert gate it currently lacks.
- **No live contamination from shadow** — shadow streams are physically distinct (`.shadow`); shadow risk-state is a distinct key; order_router paper writes no risk counters. A shadow run cannot trip the live kill_switch or move live caps.
- **Backward compatibility** — `RuntimeRiskState.key_suffix` defaults to `""`; the stock chain and all current callers are byte-for-byte unaffected. The futures live forms are renamed (`stream:signal.*` → `signal.*.futures`), which is safe because the chain is dormant (all four futures systemd units default `off`; the only `stream:signal.*` references elsewhere are Prometheus counters, not stream consumers). See §9 risk note on out-of-band paper runs.
- **Consumer-group continuity** — group names unchanged, so no group re-creation needed; renaming the *stream* a group reads from simply points the group at the new stream (groups are per-stream, created on first `xreadgroup` via `MKSTREAM`-style ensure in `StreamStage`).

## 7. Testing

Mirror the stock daemons' stream-name tests. All under `tests/`, run with `.venv/bin/pytest`.

- **decision_engine** (`tests/unit/decision_engine/test_shadow_wiring.py`, `tests/unit/services/test_decision_engine_main.py`): update the live/off assertion from `stream:signal.candidate` to `signal.candidate.futures`; keep the shadow assertion `signal.candidate.futures.shadow`. Add `_resolve_mode` default/normalization coverage if absent.
- **risk_filter** (`tests/unit/services/test_risk_filter_main.py` + a new `_resolve_mode`/`_streams_for` unit test): assert `_streams_for("shadow")`/`("live")` return the correct `(candidate, final)` pairs; assert off-inert; assert the risk-state key suffix in shadow (`risk:state:futures:shadow`).
- **order_router** (`tests/unit/services/test_order_router_main.py`): assert `_final_stream_for`/`_fill_stream_for` for paper (`.shadow`) and live; keep the existing F-3 `_resolve_mode` off/paper/live tests green.
- **RuntimeRiskState** (`tests/unit/risk/…`): assert `key_suffix` produces `risk:state:futures:shadow` (+ `:shadow:meta`) and that default `""` is unchanged.
- **Integration** (`tests/integration/test_signal_to_fill_e2e.py`, `tests/integration/test_futures_strategy_daemon_shadow.py`): update the pinned stream-name constants to the new bases; confirm the full shadow chain connects (candidate.shadow → final.shadow → fill.shadow) and the live chain connects on unsuffixed names.
- **Regression**: full `tests/` gate (CI-parity 2-pass: `-m "not serial" -n auto` then `-m serial`), mypy on changed `shared/` files, black/ruff.

## 8. Out of scope (explicit)

- Enabling a shadow run (systemd `Environment=` edits — operator step).
- **F-2** decision_engine live producer (today's `live` context provider is an inert stub; F-1 only fixes the *name* it would publish to).
- Shared-helper DRY extraction (`shared/streaming/signal_streams.py` migrating both chains) — deferred; F-1 uses per-module helpers.
- Futures monitor daemon + dashboard `trading:futures:*` `:shadow` wiring (no futures monitor exists in the decoupled chain) — separate increment.
- A shadow kill_switch — the shadow pipeline runs without one; the live kill_switch is unaffected.
- Orderbook streaming transport — order_router uses its own real WS (F-3 decision), unchanged.

## 9. Risks / open items

- **Out-of-band paper run during rename.** F-3 just shipped `FUTURES_ORDER_ROUTER=paper`. If an operator has a paper order_router running against the old `stream:signal.final`, the rename silently detaches it. Mitigation: the chain is documented dormant and units default `off`; confirm no manual paper run is live before merge (it consumes `stream:signal.final` today; post-F-1 it consumes `signal.final.futures.shadow`).
- **Asymmetry with stock is intentional.** Futures suffixes risk-state in shadow; stock does not. Documented in code comments + memory so a future reader doesn't "fix" the divergence.
- **Env-var inconsistency persists by choice.** `FUTURES_STRATEGY_DAEMON` / `FUTURES_RISK_FILTER` / `FUTURES_ORDER_ROUTER` use three different nouns; renaming for symmetry was rejected as a needless behavior change. The shadow pipeline is `=shadow,=shadow,=paper` and the live pipeline is `=live,=live,=live` — documented in the runbook follow-up (F-9).

## 10. Acceptance criteria

1. Each futures daemon derives every stream name from a `_resolve_mode()` + per-mode stream helper; no hardcoded `stream:signal.*` / `stream:order.fill` literals remain in the chain.
2. decision_engine `shadow`/`live` and risk_filter `shadow`/`live` and order_router `paper`/`live` agree on stream names so each pipeline connects end-to-end (shadow on `.shadow`, live unsuffixed).
3. risk_filter is off-inert by default and reads `risk:state:futures:shadow` in shadow mode; `RuntimeRiskState` gains a backward-compatible `key_suffix` (default `""`).
4. order_router paper writes no live risk counters (already true; covered by a regression test/assertion).
5. Stock chain and all existing `RuntimeRiskState` callers are unchanged (default suffix `""`).
6. Tests updated/added per §7; full gate green; mypy/ruff/black clean.
