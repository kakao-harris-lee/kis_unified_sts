# Futures Strategy Track A — Trailing Exit + Daily Directional Bias + Crash Guard

- **Date:** 2026-06-21 (KST)
- **Status:** Design approved; spec for implementation planning
- **Scope:** Futures paper path (monolithic `trader-futures` orchestrator). Live remains gated.
- **Supersedes for futures exit/entry-filter behavior:** the fixed-bracket exit on Setup A/C.

## 1. Problem (diagnosed, data-backed)

Current futures setups (`setup_a_gap_reversion`, `setup_c_event_reaction`) are **mean-reversion** entries and keep long/short symmetry. Their exit is `shared/strategy/exit/setup_target_exit.py` — **fixed stop / fixed take-profit / EOD only**. No trailing, no momentum exit, no time-based partial.

- Stop = 3.5×ATR (Setup A, `config/strategies/futures/setup_a_gap_reversion.yaml`), but 1-minute ATR ≈ 0.08% of price → stop ≈ 0.28%, i.e. **1-minute noise width**. Fast stop-outs are structural.
- Ledger (`data/runtime/paper/runtime.db`, `trades`): **7 futures trades total, all 2026-06-09..06-11** (before PR #479). `stop_loss` ×4, **median/avg hold 5.7 min (min 3.0)**, avg −0.79%. **Zero trades since 06-11** → PR #479's stop widening is unverified.
- **No daily directional bias** mechanism and **no futures crash (急落) guard** exist today.

Operator goal: *focus on current signals → set a daily directional bias → unless a crash pattern appears, HOLD and maximize return.* The "too fast exit" and "0 trades" are the two complaints.

## 2. Goal / Non-Goals

**Goal (Track A):** Keep the validated mean-reversion *entries*; change *exit*, add a *daily directional entry filter*, and add a *crash guard* so that:
- winners are held via a **trailing exit** instead of a fixed target ("hold until it turns");
- the normal stop is **widened** because tail risk is handled by an explicit **crash guard**, reducing noise stop-outs;
- entries align to a **single daily direction** (long-only / short-only / flat).

**Non-Goals (explicitly deferred):**
- **Track B** — a *directional/trend entry* strategy ("set direction and trend-follow"). Contradicts walk-forward evidence (intraday futures mean-reverting; trend strategies collapse: macd_ema −106%, williams_r −14, momentum bankrupt). Pursued only on a **separate backtest/holdout validation track**; not enabled without passing promotion gates.
- **Setup C event-calendar sparsity** — Setup C effectively never fires due to the manual static `scheduled_events.yaml`. Separate follow-up (event sourcing), not this spec.
- **Overnight holding** — "당일(daily) direction" ⇒ intraday; EOD close (15:15 KST, capped at 15:30 exchange close) is retained.

## 3. Paradigm reconciliation (why this is safe)

The operator's "hold and maximize" is achievable **without resurrecting a known-failing trend entry**: the fast exits are caused by the *exit* (noise-width stop + fixed target), not by an entry edge. We keep mean-reversion entries and only let winners run via a trailing exit, with a crash guard for tail risk. Whether a trend-following *exit* sits well on a mean-reversion *entry* is the **central hypothesis to validate in backtest** (a retrace entry that then trend-rides). If it does not hold up, tuning levers are `trail_atr_mult` and an optional momentum-decay assist.

## 4. Components

Each unit has one purpose, a defined interface, and is independently testable.

### 4.1 `DailyBiasProvider` — new, `shared/decision/daily_bias.py`
- **Purpose:** Produce a single per-day direction `long | short | flat`.
- **Input:** LLM market context (`overall_signal`, `regime`, `confidence`) as already surfaced to the orchestrator; the trading clock (KST).
- **Logic:** On the first valid context after open (or first evaluation tick), map `overall_signal` → direction (STRONG/MODERATE BULLISH → long; BEARISH → short; neutral → flat). Require `confidence ≥ bias_min_confidence` (default 0.5) else `flat`. Optionally veto by `regime` (e.g. strong-bear regime forces non-long) — **reuse the adapter's existing regime config (`long_blocked_regimes`) rather than duplicating a second regime list** (DRY); the `non_long_regimes` knob below should reference/derive from it, not restate it. Persist to Redis `trading:futures:daily_bias` (value + computed-at), **TTL to EOD**. Idempotent for the day (compute once, then read).
- **Interface:** `get_or_compute_bias(context, now_kst) -> Literal["long","short","flat"]`; pure mapping helper `bias_from_context(...)` for unit tests.
- **Depends on:** Redis DB1, LLM context dict, market clock.

### 4.2 Entry bias filter — extend `shared/strategy/entry/setup_adapters.py`
- **Purpose:** Gate setup entries to the daily direction.
- **Logic:** After existing gates (RegimeGate, LLM veto, time/macro), require `signal_direction == daily_bias`; if `bias == flat`, block all new entries. Emits a reject reason `daily_bias_misaligned` / `daily_bias_flat` into the existing `last_reject_reason` + Redis `trading:futures:setup_eval` observability (PR #483) so "why 0 trades" stays answerable.
- **Invariant:** long/short symmetric (the filter treats both directions identically).

### 4.3 Composed exit — `ChandelierTrailExit` + `CrashGuard` (+ backstop + EOD)
Replaces `setup_target_exit` for futures Setup A/C. Built from existing assets where possible (`shared/strategy/exit/chandelier_exit.py`, `momentum_decay.py`).
- **Trailing (primary, "maximize"):** Remove the fixed `take_profit`. Trail = running favorable-extreme − `trail_atr_mult`×ATR (default 3.0), activated once the position is in profit by `trail_activate_atr_mult` (default 1.0). Exit only when price crosses the trail → ride the move until it reverses.
- **Crash guard (急落):** If a single 1-minute move against the position exceeds `crash_atr_mult`×ATR (default 3.5), **force-exit immediately** and **block new entries for `crash_cooldown_minutes`** (default 30). This is what lets the normal stop widen.
- **Catastrophic backstop:** A wide hard stop at `catastrophic_atr_mult`×ATR (default 6.0) in case trail/guard miss.
- **EOD:** retain 15:15 KST (capped at 15:30) close — priority over the above is: crash guard → catastrophic stop → trail stop → EOD (evaluate in a deterministic order documented in code).
- **Interface:** an exit generator returning the same exit signal shape as `setup_target_exit` (drop-in), so the orchestrator wiring is unchanged.
- **Invariant:** symmetric for long/short; all multiples from config.

## 5. Configuration (all knobs YAML, no hardcoding)

New block under `config/strategies/futures/` (shared exit/risk config, e.g. `track_a_exit.yaml`, or per-setup blocks), defaults above:

```yaml
daily_bias:
  enabled: true
  bias_min_confidence: 0.5
  non_long_regimes: [BEAR_STRONG, BEAR_MODERATE]   # force non-long
trailing_exit:
  trail_atr_mult: 3.0
  trail_activate_atr_mult: 1.0
crash_guard:
  crash_atr_mult: 3.5
  crash_cooldown_minutes: 30
catastrophic_stop:
  catastrophic_atr_mult: 6.0
eod_close_kst: "15:15"   # effective_close_time caps to 15:30 exchange close
```
`enabled` flags allow falling back to the legacy fixed-bracket exit (rollback path).

## 6. Data flow

```
open → LLM context → DailyBiasProvider → Redis trading:futures:daily_bias (TTL=EOD)
setup entry signal → [RegimeGate/veto/time] → [signal_direction == daily_bias?] → enter
holding → ChandelierTrail tracks favorable extreme ──┬─ crash guard (Δ>crash_atr_mult×ATR adverse) → force exit + cooldown
                                                     ├─ catastrophic backstop (6×ATR) → exit
                                                     ├─ trail stop crossed → exit (lock profit)
                                                     └─ EOD 15:15 → exit
```

## 7. Behavior change

| | Now | Track A |
|--|-----|---------|
| Exit | fixed 3.5×ATR stop + fixed target → ~5.7 min stop-outs | trailing (ride trend), normal stop widened; backstop 6×ATR |
| Tail risk | narrow stop = noise stop-outs | explicit crash guard handles tail |
| Direction | per-signal, ad hoc | single daily bias (long/short/flat) accumulation |

## 8. Testing (unit, hermetic)

- `DailyBiasProvider`: mapping (signal→direction), confidence threshold → flat, regime veto, Redis persist/read idempotency, TTL.
- Entry bias filter: pass on aligned direction, block on misaligned, block all on flat; reject-reason emitted; symmetry.
- `ChandelierTrailExit`: trail activates only in profit, tracks favorable extreme, exits on cross; long & short symmetric.
- `CrashGuard`: triggers on adverse Δ>k×ATR; cooldown blocks re-entry; no false trigger on favorable spike.
- Ordering: crash > catastrophic > trail > EOD precedence.
- Config-driven: all thresholds read from YAML; `enabled:false` restores legacy exit.

## 9. Validation & rollout

- **Backtest with holdout split** (LookaheadGuard) to test the **central hypothesis** (trailing exit on mean-reversion entry) and to tune `trail_atr_mult` / decide on a momentum-decay assist. Compare vs current fixed-bracket on the same data.
- **Paper observation** on `trader-futures` after deploy; watch holding-time distribution shift and PnL; RegimeGate + counterfactual path retained.
- **No live** without Phase-5 promotion gates + operator written approval (`config/futures_live.yaml::enabled` + Redis `futures:live:suspended`). Track A is paper-first.
- **Rollback:** set `enabled:false` on the new blocks → legacy fixed-bracket exit + no bias filter.

## 10. Open follow-ups (out of scope, recorded)

- Setup C event-sourcing (calendar sparsity → effectively no fire).
- Track B directional/trend entry — separate spec + backtest/holdout validation track.

## 11. File-level change map (for the implementation plan)

- **New:** `shared/decision/daily_bias.py`; new exit generator(s) under `shared/strategy/exit/` (reuse `chandelier_exit.py`; add crash-guard + composed exit); `config/strategies/futures/track_a_exit.yaml`.
- **Edit:** `shared/strategy/entry/setup_adapters.py` (bias filter + reject reasons); wire the composed exit for Setup A/C (registry / `services/trading/orchestrator.py` exit selection); `config/strategies/futures/setup_a_gap_reversion.yaml` + `setup_c_event_reaction.yaml` (point exit to Track A, keep legacy under flag).
- **Tests:** `tests/unit/...` for each component above.
- **Unchanged:** entry signal logic of Setup A/C; long/short symmetry; EOD cap; RegimeGate/veto/observability plumbing.
