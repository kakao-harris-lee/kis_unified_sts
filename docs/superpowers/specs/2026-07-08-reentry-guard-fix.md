# Re-entry Guard Fix (RC4) — Design

- Date: 2026-07-08
- Status: implemented + verified
- Branch: `fix/reentry-guard-strategy-key`
- Owner: futures execution

## Motivation

2026-07-07 diagnosis follow-up (RC4). The post-exit re-entry guard
(`services/trading/reentry_guard.py`, wired in the orchestrator, configured in
`execution.yaml::entry_reentry_guard`) is **enabled with a 30-min futures
stop_loss cooldown** — yet on 07-07 Setup D re-entered **1-2 minutes** after each
stop. The guard silently never fired.

## Root cause

Under `scope: symbol_strategy` the cooldown key is `f"{code}:{strategy}"`.
`record_recent_exit_cooldown` resolved the strategy from the **exit** signal
first (`signal.strategy or closed.strategy`), and a real exit signal carries the
exit *generator's* name — `setup_target_exit.py:252` sets `strategy=self.name` =
`"setup_target_exit"`. So the cooldown was recorded under
`A01609:setup_target_exit`, but the entry check keys on the **entry** strategy
(`A01609:setup_d_vwap_reversion`). The keys never match → the guard is a no-op
for every setup whose exit generator name ≠ entry strategy name (all of Setup
A/C/D, and stock strategies using shared exit generators).

The existing tests missed this because they set the exit signal's `strategy` to
the *entry* name (e.g. `"momentum_breakout"`), which the real exit path never
does.

## Fix

1. **Key on the position's (entry) strategy.** `record_recent_exit_cooldown` now
   resolves `closed.strategy or signal.strategy` (position first). The recorded
   key matches the entry key, so the guard fires. Backward-compatible with the
   existing tests (there `closed.strategy == signal.strategy`). New regression
   test uses the realistic mismatch (exit `setup_target_exit`, entry
   `setup_d_vwap_reversion`).

2. **Retune the futures stop_loss cooldown 1800s → 180s (3 min).** With the guard
   fixed, the dormant 30-min value would suddenly bite and cut the reversal wins
   (see below). The active futures setups are mean-reversion, where the reversal
   that ends a losing streak IS the win, so the cooldown must stay short.
   Env-overridable (`FUTURES_REENTRY_STOP_LOSS_COOLDOWN_SECONDS`).

## Verification (07-07 replay, real guard semantics)

| stop / target cooldown | trades | net pts | reversal wins cut |
|---|---|---|---|
| **actual (guard dead)** | 13 | −8.4 | 0 |
| 30 min / 10 min (old config, if it worked) | 6 | −12.1 | 1 |
| **3 min / 0** | 10 | **+10.1** | 0 |
| 5 min / 0 | 9 | −29.1 | 1 |

A 3-min stop_loss cooldown skips exactly the three sub-3-min impulsive re-chases
(all losers) while keeping both reversal wins (the +39 at 14:28 was 4 min after a
stop — a 5-min cooldown would cut it). **Caveat: this is one day and the margin is
thin (fragile at ~4 min).** The fix (guard actually functioning) is the durable
win; the 3-min value is a validated-on-one-day starting point, tunable via env,
to confirm in paper.

## Scope

Bug fix + a config retune. No new mechanism (the guard already existed). Stock
cooldowns unchanged (30-min stop_loss is appropriate for momentum strategies).
Remaining diagnosis follow-up: RC3 opening-auction spread guard.
