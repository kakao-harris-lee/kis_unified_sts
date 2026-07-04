# MarketContext Builder Unification (F-4) — Design

**Status:** Approved (design) — 2026-06-07
**Scope unit:** F-4 of the futures-decoupling roadmap (Phase B, last item). Depends on nothing beyond the existing builders. Small DRY refactor + an invariant test.

---

## 1. Problem

Two code paths build the decision-engine `MarketContext`:
- **Decoupled:** `services/decision_engine/context_provider.py::FuturesContextProvider.__call__` — pulls from the daemon indicator engine + parquet daily reference + Redis macro + events YAML. Hardcodes `vwap=0.0`, `atr_90th_percentile=0.0`, `current_spread_ticks=0.0` (comments: "unused by Setup A/C", "no orderbook in raw_data").
- **Orchestrator:** `shared/strategy/entry/setup_adapters.py::_build_market_context` — reconstructs from `context.market_data`/`context.indicators` dicts (with a fast-path that returns an already-built `MarketContext`). Defaults `vwap→current_price`, `atr_90th_percentile→atr_14*1.5`, `current_spread_ticks→1.0`.

The two builders **duplicate the `MarketContext` assembly** and **disagree on the default policy** for the three fields that Setup A and Setup C provably never read (`vwap`, `atr_90th_percentile`, `current_spread_ticks`). This is the memory's flagged "builder drift". The divergence has **no signal impact today** (A/C read none of the three), but it is genuine duplication + a latent inconsistency a future Setup could trip over.

## 2. Goal

Extract a single canonical `MarketContext` assembler that both paths call, with one agreed default policy, and add an invariant test that locks the "Setup A/C ignore these three fields" property so the duplication can never silently re-diverge into a signal bug.

## 3. Approach (decided)

1. **Canonical assembler** `build_market_context(...)` in `shared/decision/context.py` (module function, alongside `MarketContext` + `load_scheduled_events`). Takes the raw field values; applies the default policy for the three unused fields; returns a `MarketContext`.
2. **Default policy = orchestrator heuristics** (operator decision): `vwap → current_price`, `atr_90th_percentile → atr_14 * 1.5`, `current_spread_ticks → 1.0`. → **zero behavior change for the live orchestrator path**; the decoupled path's `0.0 → non-zero` is invisible (A/C don't read them; the `MarketContext` fields aren't serialized downstream — only the resulting `Signal` is published).
3. **Both call sites delegate assembly** to the function. The raw-value *extraction* is NOT unified (the two sources are genuinely different: an indicator-engine object vs `market_data`/`indicators` dicts) — only the assembly + default policy is shared.
4. **Invariant test:** Setup A and Setup C produce identical signals regardless of the three fields' values.

## 4. Design

### 4.1 `build_market_context` (`shared/decision/context.py`)

```python
def build_market_context(
    *,
    now: datetime,                       # KST-aware (caller normalizes)
    symbol: str,
    current_price: float,
    prev_close: float,
    today_open: float,
    atr_14: float,
    last_15min_high: float,
    last_15min_low: float,
    vwap: float | None = None,
    atr_90th_percentile: float | None = None,
    current_spread_ticks: float | None = None,
    macro_overnight: object | None = None,
    scheduled_events: list[ScheduledEvent] | None = None,
) -> MarketContext:
    """Assemble a MarketContext with the canonical default policy.

    Setup A and Setup C read NONE of ``vwap`` / ``atr_90th_percentile`` /
    ``current_spread_ticks`` (locked by the F-4 invariant test). They are
    assembled here with shared defaults so the decoupled and orchestrator
    builders stay consistent: vwap→current_price, atr_90th→atr_14*1.5,
    spread→1.0. ``current_spread_ticks`` is uncomputable from the OHLCV-only
    tick stream, so the decoupled path always takes the default.
    """
    return MarketContext(
        now=now,
        symbol=symbol,
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        vwap=vwap if vwap is not None else current_price,
        atr_14=atr_14,
        atr_90th_percentile=(
            atr_90th_percentile if atr_90th_percentile is not None else atr_14 * 1.5
        ),
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        current_spread_ticks=(
            current_spread_ticks if current_spread_ticks is not None else 1.0
        ),
        macro_overnight=macro_overnight,
        scheduled_events=list(scheduled_events) if scheduled_events else [],
    )
```

### 4.2 Decoupled call site (`FuturesContextProvider.__call__`)

Replace the inline `MarketContext(...)` (lines 82-96) with a `build_market_context(...)` call passing the computed raw values and **omitting** vwap/atr_90th/spread (→ canonical defaults). Net effect: `vwap 0.0→current_price`, `atr_90th 0.0→atr_14*1.5`, `spread 0.0→1.0` — invisible to A/C. Everything else (warm/ATR guards, daily_ref.observe, macro/events handling) unchanged.

### 4.3 Orchestrator call site (`_build_market_context`)

Keep the fast-path (return `context.market_context` if it is a `MarketContext`) and the `_get_float` extraction + timestamp/events/macro logic unchanged. Replace the final `MarketContext(...)` (lines 439-453) with `build_market_context(...)` passing the extracted values explicitly (it already computes `vwap`/`atr_90th`/`spread` via `_get_float` defaults — pass them through, so orchestrator behavior is byte-identical).

### 4.4 Invariant test

A new test constructs a Setup A context and a Setup C context, generates a signal, then re-generates with `vwap`/`atr_90th_percentile`/`current_spread_ticks` set to wildly different values (e.g. 0.0 vs 9999.0), and asserts the emitted signal (direction + entry/stop/target + whether a signal fires) is identical. This locks the premise so any future code that reads one of these fields in A/C breaks the test loudly.

## 5. Error handling / safety

- **No signal/behavior change:** orchestrator path keeps its exact defaults (zero change); decoupled path's unused-field values change but are never read (invariant test proves it) and never serialized (only the `Signal` is published downstream).
- **Back-compat:** `build_market_context` is additive; `MarketContext` is unchanged; the only test update is `test_context_provider.py`'s `current_spread_ticks == 0.0 → == 1.0` assertion (and optionally new vwap/atr_90th assertions).
- **No new dependencies / no cross-layer leak:** the function lives next to `MarketContext` in `shared/decision/context.py`; both callers already import from there.

## 6. Testing

- **`build_market_context` unit tests** (`tests/unit/decision/test_build_market_context.py`): defaults applied when the three are omitted (vwap==current_price, atr_90th==atr_14*1.5, spread==1.0); explicit values honored when passed; scheduled_events None→[].
- **Decoupled** (`tests/unit/decision_engine/test_context_provider.py`): update `current_spread_ticks == 0.0` → `== 1.0`; add `vwap == current_price` + `atr_90th_percentile == atr_14 * 1.5` assertions; all other assertions unchanged (current_price/atr_14/prev_close/today_open/ranges/macro/events).
- **Orchestrator** (`tests/unit/strategy/test_setup_adapters_regime_gate.py` + any setup_adapters tests): must stay green (behavior byte-identical).
- **Invariant** (`tests/unit/strategy/test_setup_ac_field_invariance.py`): Setup A + Setup C signals identical under varied vwap/atr_90th/spread.
- Full CI-parity gate; mypy on `shared/decision/context.py`; ruff/black.

## 7. Out of scope

- Unifying the raw-value *extraction* (genuinely different sources — engine object vs dicts).
- Computing a real VWAP or spread for the decoupled path (the OHLCV tick stream has no orderbook; would require an ingest-layer change — not a builder concern). If a future Setup needs them, that is a separate ingest + Setup change, at which point this single assembler is the one place to wire them.
- F-2 (decision_engine live producer), F-8/F-9 cutover.

## 8. Acceptance criteria

1. A single `build_market_context(...)` in `shared/decision/context.py` assembles `MarketContext` with the canonical default policy (vwap→current_price, atr_90th→atr_14*1.5, spread→1.0).
2. Both `FuturesContextProvider.__call__` and `_build_market_context` delegate assembly to it; the orchestrator path's behavior is byte-identical; the decoupled path's three unused fields change to the canonical defaults (no signal impact).
3. An invariant test locks that Setup A and Setup C ignore vwap/atr_90th_percentile/current_spread_ticks.
4. All existing builder tests stay green (only the documented `current_spread_ticks` assertion updates); full gate green; mypy/ruff/black clean.
