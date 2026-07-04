# Stock Bear-Gate Per-Symbol Override — Design Spec (Component A)

**Status:** Draft for review
**Date:** 2026-06-22
**Sibling (shipped):** Component B — intraday symbol prewarm (MERGED #504). This is
the SECOND sub-project; design decisions below were operator-chosen via Q&A.
**Branch:** `feat/stock-bear-gate-override`

## Goal

Let individually-strong stocks bypass the **blanket market bear gate** so the
decoupled stock pipeline can enter (and hold) confirmed-uptrend names during a
market-wide bear regime, instead of skipping the entire universe on a single
market-median-MFI switch.

## Problem

The bear gate is enforced on BOTH sides of the decoupled stock pipeline, keyed
to one market-wide regime (median MFI over the universe → `MarketClassifier`):

- **Entry (M4-P):** `services/stock_strategy/daemon.py:121-133` — when the regime
  is BEAR_* and `block_entries_in_bear`, `evaluate_once` does `return 0`, skipping
  the entire per-symbol loop.
- **Exit (M4-X):** `shared/strategy/exit/three_stage.py:417-429` — when
  `enable_bear_exit` and the market is bear, EVERY open position is liquidated
  with `BEAR_EXIT` at priority 1.

On 2026-06-22 the regime was BEAR_STRONG (median MFI ≈ 28) while 6 of 9
screener trade-targets were individually strong (SK하이닉스 +5.3% RSI74,
한솔테크닉스 +21%, 제주반도체 +16%, 후성 +8.7%, 삼성전자). All were blocked from
entry and would have been instantly bear-exited — the gate ignores per-symbol
strength. M4-X has **no indicator engine** (M4-P owns the only one), so the exit
side cannot compute strength itself; it must consume a published verdict.

## Design (operator-chosen)

Mirror the existing M4-P→Redis→M4-X regime contract
(`shared/streaming/stock_regime.py`) with a second per-symbol contract:

```
M4-P (StockStrategyDaemon), each eval cycle:
  ├─ read system:daily_indicators:latest  (per-symbol daily indicators)
  ├─ compute_strong_symbols(indicators, cfg)  → set of "strong" codes
  ├─ publish set → Redis stock:daemon:bear_override  (TTL + computed_at_ms)
  └─ [entry] if bear regime: evaluate ONLY strong-set symbols (capped),
             tag candidates metadata{bear_override:true}; non-bear: unchanged
M4-X (StockExitDaemon), each scan:
  ├─ _load_bear_override()  → strong set (staleness-gated, like _load_market_state)
  └─ scan_positions(..., bear_override_symbols=set)
        → ThreeStageExit skips the BEAR_EXIT branch when position.code ∈ set
```

A strong stock is therefore **neither blocked from entry nor bear-dumped** while
it stays strong; when it weakens it drops out of the set on the next cycle and
normal bear behavior resumes (re-evaluated, not sticky).

### Strength definition (multi-factor trend AND — config thresholds)
A symbol is strong iff ALL hold (inputs from `system:daily_indicators:latest`):
- `daily_close > daily_sma_20`
- `daily_rsi_14 >= rsi_min` (default 55)
- `daily_rsi_14 > daily_prev_rsi_14` (RSI rising)
- `daily_macd_hist > 0`

This is a coarse "worth evaluating despite market bear" filter; the actual entry
decision still runs the existing strategy logic (momentum_breakout etc.).
Verified against 2026-06-22 data: passes SK하이닉스/삼성전자/제주반도체/한솔테크닉스/후성,
rejects LG전자/대우건설/대한광통신.

### Concurrent cap (risk)
Normal position sizing. Bound concurrent override exposure: before emitting
override candidates in a bear cycle, M4-P reads the open-positions hash
(`stock_daemon_positions_key()`, field=code) and counts open positions whose code
is in the current strong-set; if `>= max_override_positions`, emit no new
override candidates this cycle.

## Components / file changes

### New: `shared/strategy/symbol_strength.py`
Pure, unit-testable:
```python
@dataclass(frozen=True)
class StrengthCriteria:
    rsi_min: float = 55.0
    require_above_sma20: bool = True
    require_rsi_rising: bool = True
    require_macd_positive: bool = True

def is_strong(daily: dict, criteria: StrengthCriteria) -> bool: ...
def compute_strong_symbols(indicators_by_code: dict[str, dict], criteria) -> set[str]: ...
```
`indicators_by_code` is the `indicators` map from `system:daily_indicators:latest`.
Missing/non-finite fields → that symbol is NOT strong (conservative).

### New: `shared/streaming/stock_bear_override.py`
Mirror `stock_regime.py`: `BearOverrideConfig` (frozen dataclass + `load()`),
`compute_override_payload(strong: set, *, now_ms) -> dict`
(`{"strong": [...], "count": n, "computed_at_ms": ms}`),
`publish` via `redis.set(key, json, ex=ttl)`, and
`parse_strong_set(raw, *, config, now_ms) -> set[str]` with the SAME positive-form
staleness gate as `parse_market_state` (`if not 0 <= age <= max_age: return set()`)
— stale/missing/malformed/NaN → empty set (fail-safe to normal bear behavior).
Config fields: `enabled` (code default False), `redis_key`
(`stock:daemon:bear_override`), `publish_ttl_seconds` (900), `max_age_seconds`
(300), `max_override_positions` (cap), plus the `StrengthCriteria` thresholds.

### Modify: `services/stock_strategy/daemon.py`
- `__init__`: accept `bear_override_config: BearOverrideConfig | None` +
  `daily_indicators_key: str` (default `system:daily_indicators:latest`).
- `evaluate_once`: after `_publish_regime`, when override enabled:
  - read daily indicators, `strong = compute_strong_symbols(...)`,
    `publish_override(strong)` (always publish when enabled — observability).
  - In the bear branch (currently `return 0`): if override enabled and `strong`
    non-empty, iterate ONLY `[s for s in universe if s in strong and is_warm(s)]`,
    enforce `max_override_positions` via the positions-hash count, tag emitted
    signals `metadata["bear_override"]=True`. Otherwise keep `return 0`.
  - Non-bear cycles unchanged.
- Best-effort: any failure computing/publishing strength → behaves like today
  (full bear block); log, never raise.

### Modify: `shared/strategy/exit/three_stage.py`
- `scan_positions` + `_check_position` accept `bear_override_symbols: set[str] |
  None = None`.
- In the bear-exit branch (line ~418): `if self.config.enable_bear_exit and
  self._is_bear_market(market_state) and position.code not in (bear_override_symbols
  or set()):` → skip BEAR_EXIT for override symbols, fall through to normal
  stage/stop/time/EOD exits. Default `None` → today's behavior (no caller change
  breaks).

### Modify: `services/stock_exit/daemon.py` + `main.py`
- Add `_load_bear_override()` mirroring `_load_market_state()` (read the override
  key, `parse_strong_set` staleness-gated → set, empty on any problem).
- Pass `bear_override_symbols=await self._load_bear_override()` into
  `scan_positions(...)`. Wire `BearOverrideConfig.load()` in main (None when
  disabled → empty set → today's behavior).

### Config: `config/stock_bear_override.yaml` (section `stock_bear_override`)
All thresholds/limits config-driven; `enabled` code-default False, paper YAML
enables. Mirrors `stock_regime.yaml` load pattern (defaults on any failure).

## Error handling / safety
- **Fail-safe to normal bear behavior** everywhere: strength-compute failure,
  publish failure, stale/missing/malformed override key → empty strong set →
  entry stays blocked AND M4-X bear-exit fires normally. Never exempt a position
  on bad/stale data (same invariant as the regime staleness gate; positive-form
  age bound rejects NaN).
- Override only matters in BEAR regime; non-bear cycles are untouched.
- `enabled=False` (code default) ⇒ zero behavior change vs main.
- Positions-hash read failure → skip override entries this cycle (conservative).
- KST trading logic preserved (epoch-ms timestamps, tz-agnostic). Redis DB 1,
  new key gets a TTL. Long-only preserved; no new EOD liquidation.

## Observability
- M4-P INFO: `bear override: N strong (codes) — evaluating override entries` /
  per-entry log with the criteria values; cap-reached log.
- M4-X INFO: `bear-exit skipped for <code> (override)`.
- Metrics: `stock_bear_override_strong{}` (gauge), `..._entries_total`,
  `..._exit_skips_total`.

## Testing
- `symbol_strength`: truth table per AND-condition; the 2026-06-22 fixture
  (6 strong / 3 weak); missing/NaN fields → not strong.
- `stock_bear_override`: publish round-trip; `parse_strong_set` staleness
  (fresh→set, stale→∅, missing→∅, NaN-age→∅).
- M4-P `evaluate_once` in bear: only strong+warm symbols evaluated; cap enforced
  via positions hash; candidates tagged; override key published; non-bear cycle
  unchanged; failure → `return 0` (fail-safe).
- M4-X `three_stage`: BEAR_EXIT skipped for code in fresh strong-set; fired for
  weak code; fired when override set stale/empty (fail-safe); default None → today.

## Scope / out of scope
- **In:** the two-sided per-symbol override (entry + exit), strength module,
  override Redis contract, config, observability.
- **Out:** changing the market regime computation itself; futures (untouched);
  Component B prewarm (shipped); the orchestrator path (decoupled stock only).
- **Rollout:** paper-only via config (`enabled` code-default False, paper YAML
  true); deploy = rebuild `stock-strategy` + `stock-exit`, `up -d --no-deps`
  (never `down`). Observe the override metrics + that strong names enter/hold
  during a bear regime while weak names stay blocked/bear-exited.
