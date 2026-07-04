# C1 — Look-Ahead Bias Guard for Backtest + Strategy Contract

**Status**: Draft (spec-only, no implementation in this PR)
**Date**: 2026-05-17
**Owner**: TBD
**Related**: PR #322 "Out of Scope" → C1; companion to M9 (#325), M10 (#326)

---

## 1. Problem

Backtest results are only credible if a strategy at bar `t` cannot observe any information from bars `t+1, t+2, …`. Today the platform has **no enforced contract** that prevents this. The risk surfaces in three places:

### 1.1 `EntryContext` / `ExitContext` have no temporal contract

[`shared/strategy/base.py`](../../../shared/strategy/base.py#L85-L120) defines:

```python
@dataclass
class EntryContext:
    market_data: dict[str, Any]   # OHLCV etc.
    indicators: dict[str, Any]    # precomputed series
    timestamp: datetime           # "current" time
    ...
```

Nothing in the docstring, type system, or runtime enforces that `market_data[...]` and `indicators[...]` arrays are sliced to `≤ timestamp`. A strategy that does `series.iloc[-1]` is *implicitly trusting* the caller. A strategy that does `series.iloc[idx_of(timestamp) + 1]` is undetectably cheating.

### 1.2 The backtest engine passes a single `bar` dict, but adapters build their own history

[`shared/backtest/engine.py:206`](../../../shared/backtest/engine.py#L206) — `signal = self.strategy.on_bar(bar)`. The adapter layer (`shared/backtest/adapter.py` and per-strategy `setup_adapters.py`) is responsible for:

- Accumulating an OHLCV ring buffer from successive `bar` calls
- Computing indicators
- Building an `EntryContext`

Each adapter implements this independently. There is no shared utility that guarantees "the buffer at call N contains exactly bars 0..N". Two failure modes:

- **Pre-computed full-series indicators** (e.g., `strategy.prescan_data(data)` at [`engine.py:185`](../../../shared/backtest/engine.py#L185)) can leak — the strategy holds a reference to the *entire* indicator series and only needs to look one row ahead.
- **`precompute_rl_features(data)`** at [`engine.py:181`](../../../shared/backtest/engine.py#L181) computes RL features for the whole dataset up front; the RL adapter must internally slice by current bar index, which is not externally verified.

### 1.3 Exit path has the same hole

`check_exit(bar)` at [`engine.py:267`](../../../shared/backtest/engine.py#L267) — same story. An exit strategy that "knows" tomorrow's high can fabricate a perfect trailing stop.

### 1.4 Why this matters now

`opening_volume_surge`, `momentum_breakout`, `trix_golden`, `williams_r`, `mean_reversion`, `trend_pullback`, `volume_accumulation`, and the LLM/RL strategies all hit production paper trading off backtest results. If any one of them has a quiet look-ahead bug, the live PnL gap will appear only after real capital is exposed.

---

## 2. Goals & Non-Goals

### Goals

1. Define a **single explicit temporal contract** that every entry/exit strategy adheres to.
2. Provide a **runtime enforcement mode** (opt-in, default-on for backtests) that *catches* violations rather than relying on code review.
3. Cover both the per-bar streaming path (`on_bar`) and the precomputed-series path (`precompute_rl_features`, `prescan_data`).
4. Zero behavioural change for callers that already obey the contract.

### Non-Goals

- Refactoring strategies that already comply.
- Detecting *statistical* look-ahead (e.g., overfit hyperparameters from the same backtest window) — that is C2/scope of validation, not this contract.
- Real-time guard for live trading — `services/trading/orchestrator.py` is naturally bar-by-bar; the contract still applies but enforcement cost there is unnecessary.

---

## 3. Contract Definition

### 3.1 Temporal invariant

> **For any call to `EntrySignalGenerator.generate(ctx)` or `ExitSignalGenerator.generate(ctx)` with `ctx.timestamp = T`:**
>
> - Every time-indexed value reachable from `ctx.market_data` or `ctx.indicators` MUST have its **last observation timestamp `≤ T`**.
> - Every value derived from such a series (e.g., a scalar "current RSI") MUST be the value computed **using only observations with timestamp `≤ T`**.

This is the standard *"information set at time T"* contract. `≤` not `<` because OHLCV at minute T is fully formed at minute T — a 1-minute bar timestamped 09:30 is the closed bar `[09:29, 09:30)`.

### 3.2 Explicit annotations on context types

Extend [`shared/strategy/base.py`](../../../shared/strategy/base.py):

```python
@dataclass
class EntryContext:
    """...
    Temporal contract (CRITICAL):
      Every time-indexed value in market_data and indicators MUST have its
      last observation at timestamp <= self.timestamp.
      Backtest callers MUST guarantee this. Strategies MAY rely on it.
      Violation = look-ahead bias (silent invalid PnL).
      See docs/superpowers/specs/2026-05-17-lookahead-bias-guard.md
    """
    ...
```

Same block added verbatim to `ExitContext`.

### 3.3 Allowed shapes for time-indexed values

A "time-indexed value" is one of:

| Type | Has timestamp? | Tail-check rule |
|---|---|---|
| `pandas.Series` with `DatetimeIndex` | yes | `series.index[-1] <= T` |
| `pandas.DataFrame` with `datetime` column | yes | `df["datetime"].iloc[-1] <= T` |
| `numpy.ndarray` / `list` of floats | no | length-only invariant (see §4.2) |
| scalar (`float`, `int`, `str`) | n/a | excluded |

Strategies SHOULD prefer the first two shapes so the guard can verify them. The third shape is permitted for backward compatibility; it is verified by the weaker "length must not change retroactively" rule (§4.2).

---

## 4. Enforcement Design

### 4.1 New module: `shared/backtest/lookahead_guard.py`

Single class:

```python
class LookaheadGuard:
    """Wraps EntryContext / ExitContext for runtime tail-check.

    Modes:
      OFF      — no-op (production / live).
      ASSERT   — raise LookaheadViolation on first offence (CI / backtest).
      WARN     — log.warning + continue (one-shot migration).
    """
    def check_entry(ctx: EntryContext) -> None: ...
    def check_exit(ctx: ExitContext) -> None: ...
```

Algorithm (pseudo-code):

```
T = ctx.timestamp
for source_name in ("market_data", "indicators"):
    for key, value in getattr(ctx, source_name).items():
        if hasattr(value, "index") and isinstance(value.index, DatetimeIndex):
            assert value.index[-1] <= T, f"{source_name}.{key} ends at {value.index[-1]} > {T}"
        elif isinstance(value, pd.DataFrame) and "datetime" in value.columns:
            assert value["datetime"].iloc[-1] <= T, ...
        # arrays without timestamps → §4.2 fingerprint
```

### 4.2 Fingerprint fallback for un-timestamped arrays

For `np.ndarray` / `list` series (e.g., the way many adapters pass `close_prices`), the guard cannot verify timestamps, but it CAN verify that the *length grows monotonically by exactly 1 per bar* and the *prefix is immutable*. On each call, compute a cheap fingerprint:

```python
fp = (len(value), value[0], value[-2] if len(value) > 1 else None)
```

Compare against the previous call's fingerprint for the same `(strategy_id, key)`. Violations:

- `len(value) < prev_len` → series shrunk (suspicious, but legal if window reset)
- `len(value) > prev_len + 1` → leap (likely look-ahead pre-fill)
- `value[0] != prev_first` → first element changed (data rewrite)
- `value[-2] != prev_last` → previous tail mutated (re-computation with future data)

Fingerprints are kept in a small dict (`{(strategy_id, key): (len, first, prev_last)}`); memory bounded.

### 4.3 Wiring into `BacktestEngine`

In [`shared/backtest/engine.py`](../../../shared/backtest/engine.py):

1. `BacktestConfig` gains `lookahead_guard_mode: Literal["off", "warn", "assert"] = "assert"`.
2. `BacktestEngine.__init__` constructs a `LookaheadGuard` instance when mode `!= "off"`.
3. The engine wraps `strategy.on_bar(bar)` and `strategy.check_exit(bar)` so that ANY `EntryContext` / `ExitContext` the adapter constructs is intercepted and checked before being delivered to the user strategy. Concretely: have the base adapter call `self._guard.check_entry(ctx)` inside `build_entry_context()` (and similarly for exit).
4. `precompute_rl_features` and `prescan_data` are flagged: if either is called, the guard registers the strategy as "uses pre-computed data" and applies a strict slicing assertion: every per-bar context built from those pre-computed arrays must have its slice end-index match the current bar index. The adapter exposes a `_current_bar_index` attribute; the guard reads it.

### 4.4 What happens on violation

- `ASSERT` mode: raise `LookaheadViolation(strategy=<id>, source=<market_data|indicators>, key=<name>, t=<T>, observed_t=<violating ts>)`. The backtest aborts. MLflow logs the failure as a tagged run.
- `WARN` mode: `logger.warning(...)` once per `(strategy_id, key)` to keep logs sane. Run continues. Used during the one-time audit migration of existing strategies.

### 4.5 Default mode policy

| Surface | Default | Rationale |
|---|---|---|
| `sts backtest run` (CLI) | `assert` | Catch regressions in CI before they reach traders |
| `sts optimize` (Optuna) | `assert` | Same — invalid trials must fail loudly |
| `BacktestEngine` programmatic | `assert` | Library users opt out explicitly |
| `services/trading/orchestrator.py` (live/paper) | `off` | Cost not justified; live data is bar-by-bar by construction |
| Unit tests | `assert` | Fixture data is small; test the guard alongside the strategy |

Override is per-run via `BacktestConfig.lookahead_guard_mode` or env `KIS_LOOKAHEAD_GUARD_MODE`.

---

## 5. Migration & Audit Plan (Future Work)

This spec PR does **not** implement enforcement. After approval, the implementation PR(s) will:

1. **PR-A** — Implement `LookaheadGuard`, contract docstrings, `BacktestConfig.lookahead_guard_mode` (default `"warn"` initially), guard plumbing in the base adapter. Add unit tests for the guard itself.
2. **PR-B (audit)** — Run the full backtest suite in `"warn"` mode against `artifacts/datasets/*`. Triage every emitted warning:
   - Fix the adapter / strategy
   - OR document the warning in this spec as a known false positive and refine the guard
3. **PR-C** — Flip default to `"assert"`. Add a CI smoke test that runs one backtest per registered strategy with the guard on.
4. **PR-D (optional)** — Statistical sanity: compare new (guard-on) backtest PnL distributions vs. the historical (guard-off) baseline. Any strategy whose PnL changes by `> X%` is the smoking gun.

Estimated PR count: 3–4. Each independently revertible.

---

## 6. Acceptance Criteria (for the implementation PRs, not this spec)

| # | Criterion |
|---|---|
| AC1 | `LookaheadGuard.check_entry` raises `LookaheadViolation` for a hand-crafted `EntryContext` whose `indicators["rsi"]` Series ends one bar after `ctx.timestamp`. |
| AC2 | `LookaheadGuard.check_entry` does NOT raise for a compliant context (regression guard). |
| AC3 | Fingerprint detector catches an adapter that re-emits an `np.ndarray` whose `[-2]` element changed between calls (tail mutation). |
| AC4 | `BacktestEngine(config=..., lookahead_guard_mode="assert").run(data)` aborts with `LookaheadViolation` when paired with a deliberately-cheating mock strategy that peeks one bar ahead. |
| AC5 | Same backtest in `"off"` mode runs to completion (proves no-op when disabled). |
| AC6 | Every currently-registered entry and exit strategy passes the guard in `"assert"` mode against a representative dataset slice (one-bar audit per strategy). |
| AC7 | Guard overhead `< 5%` on the `bb_reversion` futures backtest reference run (measured pre/post). |
| AC8 | Documentation in [`docs/strategies.md`](../../strategies.md) updated with the contract block and a "how to make your strategy compliant" checklist. |

---

## 7. Open Questions

1. **Adapter-level vs. strategy-level enforcement?** This spec puts the check in the adapter layer (closest to context construction). Alternative: decorate `EntrySignalGenerator.generate` with the guard. Adapter wins because some strategies skip the abstract method and override `on_bar` directly.
2. **Should the guard verify `current_positions` timestamps?** Position entry times are deterministic from the engine, low risk. Recommend: **no** for v1; revisit if a strategy starts mutating `Position` objects.
3. **What about `MarketContext` (LLM input)?** The LLM `MarketContext` is updated daily, asynchronously. Its `as_of` timestamp must be `≤ T`. Recommend: add a `MarketContext.as_of` field and let the guard check it. Defer to PR-A.
4. **RL pre-computed features in `precompute_rl_features` — strict vs. lenient slicing check?** The current RL adapter reads `features[bar_index]`. Strict check (slice must be `[:bar_index+1]`) is verifiable iff the adapter exposes `bar_index`. Recommend: require adapter to expose `_current_bar_index` as part of the contract; otherwise downgrade to fingerprint-only check.

---

## 8. References

- [`shared/strategy/base.py`](../../../shared/strategy/base.py) — `EntryContext`, `ExitContext`
- [`shared/backtest/engine.py`](../../../shared/backtest/engine.py) — main loop, `precompute_rl_features`, `prescan_data`
- [`shared/backtest/adapter.py`](../../../shared/backtest/adapter.py) — context construction
- [`shared/strategy/entry/setup_adapters.py`](../../../shared/strategy/entry/setup_adapters.py) — adapter examples
- PR #322 — "Out of Scope" item C1
- AGENTS.md §3 — strategy contract conventions
