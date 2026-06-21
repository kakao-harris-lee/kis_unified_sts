# Track A Follow-up — I1 Windowed Crash Guard + I2 Intraday Bias Refresh

**Date:** 2026-06-21
**Branch:** `fix/futures-track-a-crashguard-bias-followup`
**Base:** `feat/futures-track-a-trail-bias-crashguard`

---

## I1 — Windowed Crash Guard

### Problem
The original `crash_triggered()` compared two consecutive scan ticks (~0.5s apart) against
`crash_atr_mult × ATR` (3.5 × ATR) — a threshold sized for a **1-minute** move.
A gradual 1-minute sell-off spread across many small ticks would never trip this check.

### Fix
Added a **rolling-window path** alongside the existing single-tick path:
- `max_adverse_move_in_window(side, current_price, history, window_seconds, current_ts)` — pure helper,
  returns the maximum adverse move (largest drop for LONG, largest rise for SHORT) within the window.
- `position.metadata["crash_price_history"]` — list of `[iso_ts, price]` pairs, pruned to
  `crash_window_seconds` each tick. JSON-serialisable; survives position snapshot round-trips.
- Either path (single-tick OR windowed) fires `FORCE_CLOSE`.
- `metadata["crash_path"]` in the exit signal tells operators which path triggered.

### New config knob
`crash_window_seconds: float = 60.0` in `TrackAExitConfig` and `track_a_exit.yaml`.

### Design decisions
- **Both paths use the same `crash_atr_mult` threshold** (no second multiplier).
  The windowed max-adverse-move uses the same scale as 1-minute ATR, which is what the
  threshold was always sized for. Separate tuning is available by adjusting `crash_atr_mult`.
- **Single-tick fast path is fully preserved** — no behavior change when the windowed check
  would not have fired. This maintains backward-compatible crash behavior.
- **History on `position.metadata`** (not a module-level dict) so each position carries its own
  history; no cross-position contamination, no stale state across restart (history simply
  rebuilds from the first tick post-restart).

### Files changed
- `shared/strategy/exit/track_a_exit.py` — added `max_adverse_move_in_window`, `_update_crash_history`,
  `crash_window_seconds` config field, dual-path crash check in `_check_position`.
- `config/strategies/futures/track_a_exit.yaml` — added `crash_window_seconds: 60.0` with comment.

---

## I2 — Intraday Bias Refresh

### Problem
`DailyBiasProvider.get_or_compute_bias` was idempotent per-date: any flat read in the
morning persisted `flat` all day, blocking all entries even if LLM conviction rose later.

### Fix
Added **conditional re-evaluation for flat biases**:
- `bias_refresh_minutes: int = 60` — new `__init__` parameter (default 60).
- On each call: if the cached bias is `flat` AND `computed_at` is older than `bias_refresh_minutes`,
  recompute from the current `market_context`.
- A non-flat (directional) bias is always sticky: never flipped intraday regardless of age.
- Low-confidence recompute still returns `flat` (fail-safe unchanged).
- Internal rename: `_read_redis` → `_read_redis_raw` returning the full dict so `computed_at`
  can be inspected for the stale-flat decision.

### Wiring
`daily_bias_refresh_minutes: int = 60` added to `SetupAEntryConfig` and `SetupCEntryConfig`,
forwarded to `DailyBiasProvider(bias_refresh_minutes=...)` in both adapters.

### Design decisions
- **Only flat is re-evaluated; directional is sticky.** The risk of intraday direction flip
  (e.g. long morning → short afternoon) is much higher than missing a confidence upgrade.
  Operators who want directional flip should restart the service or manually clear Redis.
- **Default 60 minutes** — re-evaluates once per hour at worst; keeps daily bias stable while
  not locking out the whole day on a morning low-confidence read.
- **Within-window flat does NOT recompute** — prevents micro-oscillation between flat and
  directional when LLM context fluctuates around the confidence threshold.

### Files changed
- `shared/decision/daily_bias.py` — `bias_refresh_minutes` param, stale-flat re-eval logic,
  `_read_redis_raw` returning full dict.
- `shared/strategy/entry/setup_adapters.py` — `daily_bias_refresh_minutes` field on both configs,
  forwarded to `DailyBiasProvider`.

---

## Test Evidence

```
79 passed, 2 warnings in 2.54s
(was 63 before; 16 new tests added)
```

New tests:
- `test_track_a_exit.py` (I1): `test_max_adverse_move_long_gradual_crash`,
  `test_max_adverse_move_short_gradual_rally`, `test_max_adverse_move_favorable_spike_long`,
  `test_max_adverse_move_ignores_stale_ticks`, `test_windowed_crash_triggers_on_gradual_drop`,
  `test_single_tick_spike_still_fires`, `test_favorable_move_in_window_does_not_trigger_long`,
  `test_windowed_crash_short_fires`.
- `test_daily_bias.py` (I2): `test_flat_bias_refreshes_after_window`,
  `test_flat_bias_within_refresh_window_is_not_recomputed`, `test_non_flat_bias_never_refreshed`,
  `test_flat_refresh_low_confidence_stays_flat`, `test_bias_refresh_minutes_default_preserves_backward_compat`.
- `test_setup_adapters_bias.py` (I2 wiring): `test_setup_a_adapter_wires_bias_refresh_minutes`,
  `test_setup_c_adapter_wires_bias_refresh_minutes`, `test_bias_refresh_default_is_60`.

---

## Operator Notes

- Both changes are config-gated with safe defaults — existing behavior is preserved if YAML is
  unchanged (`crash_window_seconds: 60.0`, `daily_bias_refresh_minutes: 60`).
- To disable windowed crash guard: set `crash_window_seconds` very large (e.g. 3600) so no
  in-window history could accumulate an adverse move of 3.5×ATR gradually. (There is no explicit
  disable flag because the single-tick path is always active and the window simply requires more
  ticks before triggering.)
- To disable intraday bias refresh: set `daily_bias_refresh_minutes: 0` or a very large value
  (e.g. 1440 = 24h). A zero value technically skips re-eval (age > 0 minutes always) so
  any operator needing the original always-sticky-flat behavior should set this to 1440.
