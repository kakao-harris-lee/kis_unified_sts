# Momentum Breakout Trend Mode Design

**Date**: 2026-03-02
**Status**: Approved
**Goal**: Improve `momentum_breakout` strategy for strong bull markets by adding regime-aware trend mode with relaxed entry conditions and EMA pullback trigger.

## Problem

Current active stock strategies are all mean-reversion or strict breakout:
- `trend_pullback`: RSI<34 oversold bounce — too few entries in strong uptrends
- `vr_composite`: Daily VR bottom — volume depletion signals rare mid-rally
- `momentum_breakout`: N-day high breakout + RVOL>=1.6 — late entry, low return (+0.59%)

Strong bull markets produce sustained uptrends where prices rarely hit oversold levels or require high RVOL breakouts. We need a trend-following mode that enters on pullbacks within established uptrends.

## Solution: Trend Mode for momentum_breakout

Add a `trend_mode` to the existing `momentum_breakout` strategy. When the orchestrator detects `BULL` or `SIDEWAYS_UP` regime, entry conditions relax and a new **EMA pullback trigger** activates.

### Entry Changes (trend_mode=true)

**Relaxed parameters**:
| Parameter | Normal | Trend Mode |
|-----------|--------|------------|
| `rvol_threshold` | 1.6 | 1.0 |
| `breakout_buffer_pct` | 0.03 | 0.0 |
| `signal_cooldown_seconds` | 120 | 60 |

**New trigger — EMA pullback** (trend_mode only):
1. EMA alignment: `EMA5 > EMA20 > EMA60` (confirmed uptrend)
2. Pullback location: `|close - EMA20| <= ATR x ema_touch_buffer_atr`
3. Bounce confirmation: `close > EMA5` (short-term recovery)
4. Healthy RSI: `RSI > rsi_min` (40+, not oversold)
5. Volume: standard volume_ma threshold

The EMA pullback trigger fires **without requiring N-day high breakout**, allowing entries during mid-trend pullbacks.

### Exit Changes (trend_mode positions)

Exit parameter overrides stored in `signal.metadata` → `position.metadata`:

| Parameter | Normal | Trend Mode |
|-----------|--------|------------|
| `stop_atr_multiplier` | 2.0 | 2.5 |
| `trail_activation_atr` | 2.0 | 1.5 |
| `trail_atr_multiplier` | 1.5 | 2.5 |
| `max_hold_days` | 8 | 15 |

Wider trailing stop preserves uptrend momentum. Longer hold period captures extended trends.

### EMA Prewarm Strategy

EMA values are computed from candles already in memory (loaded by existing prewarm pipeline: Redis cache -> ClickHouse -> KIS REST). No additional warmup wait time required.

- `IndicatorEngine._compute_indicators()` adds `ema_5`, `ema_20`, `ema_60` absolute values and `ema_aligned` boolean
- `candle_maxlen=240` already supports 60+ candles
- `is_warm()` threshold stays at `bb_period=20` (unchanged)
- If EMA60 is unavailable (insufficient candles), only the EMA pullback trigger is disabled; N-day breakout trigger still works

### Regime Flow

```
Orchestrator._handle_regime() → self._current_regime = "BULL"
  ↓
EntryContext(metadata={"regime": "BULL", ...})  [already implemented]
  ↓
MomentumBreakoutEntry.generate(context)
  → is_trend_mode = regime in ["BULL", "SIDEWAYS_UP"]
  → Relaxed RVOL, buffer, cooldown
  → EMA pullback trigger check
  → Signal(metadata={"trend_mode": True, "exit_trail_atr_multiplier": 2.5, ...})
  ↓
Position(metadata=signal.metadata)
  ↓
ATRDynamicExit._check_position(position)
  → Reads override values from position.metadata
  → Uses wider trail, longer hold
```

## Files to Modify

| File | Change |
|------|--------|
| `shared/strategy/entry/momentum_breakout.py` | Add `TrendModeConfig` fields, trend_mode branching in `generate()`, `_check_ema_pullback()` method |
| `config/strategies/stock/momentum_breakout.yaml` | Add `trend_mode` section with all configurable params |
| `services/trading/indicator_engine.py` | Add `ema_5`, `ema_20`, `ema_60`, `ema_aligned` to `_compute_indicators()` |
| `shared/strategy/exit/atr_dynamic.py` | Read position.metadata overrides in `_check_position()` |
| `tests/test_momentum_breakout.py` | Add trend_mode test cases (normal mode, trend mode breakout, EMA pullback) |

## Config Schema (YAML)

```yaml
strategy:
  entry:
    type: momentum_breakout
    params:
      # ... existing params ...
      # Trend mode (activated when regime in trend_mode_regimes)
      trend_mode_enabled: true
      trend_mode_regimes: ["BULL", "SIDEWAYS_UP"]
      trend_rvol_threshold: 1.0
      trend_breakout_buffer_pct: 0.0
      trend_signal_cooldown_seconds: 60
      # EMA pullback trigger (trend_mode only)
      trend_ema_pullback_enabled: true
      trend_ema_fast: 5
      trend_ema_mid: 20
      trend_ema_slow: 60
      trend_ema_touch_buffer_atr: 1.0
      trend_rsi_min: 40
      # Trend mode exit overrides (passed via signal.metadata)
      trend_exit_stop_atr_multiplier: 2.5
      trend_exit_trail_activation_atr: 1.5
      trend_exit_trail_atr_multiplier: 2.5
      trend_exit_max_hold_days: 15
```

## Risk Considerations

- Trend mode only activates in BULL/SIDEWAYS_UP — BEAR regime entry block still applies
- EMA alignment requirement (EMA5>EMA20>EMA60) prevents false trend signals
- RSI > 40 filter avoids catching falling knives during pullbacks
- Position.metadata exit overrides are optional — ATRDynamicExit falls back to config defaults
- Wider stops in trend mode increase per-trade risk — compensated by higher win rate in trends

## Success Criteria

- Backtest: Trend mode increases trade count by 30%+ in BULL periods
- Backtest: Average return per trade >= 1.0% (up from 0.59%)
- Backtest: Sharpe ratio >= 3.0 (maintained)
- No regression in non-BULL regime performance
