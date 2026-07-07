# Futures Risk Circuit Breaker — Design

- Date: 2026-07-08
- Status: implemented + verified — enabled at **catastrophic-only** thresholds
- Branch: `fix/futures-risk-circuit-breaker`
- Owner: futures risk

## Motivation & root cause

2026-07-07 diagnosis follow-up (RC5): the futures daily-loss circuit breaker was
**dead**. Realized PnL *is* fed to the `RiskManager` (`record_realized_pnl` on
every close), but:

1. **Unit mismatch.** `Position.unrealized_pnl = (price − entry) × quantity` — for
   futures that is **index points**, not KRW. `RiskManager._check_daily_loss_limit`
   compares `daily_pnl_pct = daily_realized_pnl / initial_capital(=10M KRW)`
   against −5%. So −11.21 points ÷ 10M KRW ≈ **−0.0001%** → the breaker can never
   trip. This matches the live log `daily_pnl=-0.00%` after real losses.
2. **Mis-scaled model.** Even applying the KRW-per-point multiplier (KOSPI200 =
   250,000), one contract's notional (~300M) is ~30× the 10M risk capital, so a
   correct KRW %-limit would trip on the *first* trade. The %-of-capital model
   does not fit a single-contract futures book.
3. The `RiskManager` had **no consecutive-loss breaker** (the field existed only
   for adaptive sizing).

## Design

Two config-driven, futures-native breakers in `RiskManager`, reusing the existing
`record_realized_pnl` (on close) and `can_open_position` (at entry) hooks. Both
**disabled by default (0)**; the futures `risk_management.yaml` enables them.

- **Consecutive-loss halt** (`max_consecutive_losses`, unit-free): `RiskState`
  gains `consecutive_losses`, incremented on a losing close and reset on a
  winning/flat close. `can_open_position` blocks (`BlockReason.CONSECUTIVE_LOSSES`)
  once it reaches the limit.
- **Daily-loss-in-points** (`daily_loss_limit_points`): blocks
  (`BlockReason.DAILY_LOSS_LIMIT_POINTS`) when session cumulative
  `daily_realized_pnl` ≤ −limit, in the position's native unit (index points for
  futures). The orchestrator zeroes this off the futures path (meaningless
  against KRW stock PnL); the consecutive-loss breaker stays universal.

Both are session-scoped: cleared on the daily reset (auto-unblock extended to the
new block reasons). A `MANUAL` block is never auto-cleared.

## Verification — the decisive finding

Replaying today's actual 13-trade sequence through the wired breaker:

| config | trades taken | net pts | halts before |
|---|---|---|---|
| **actual (no breaker)** | 13 | **−8.4** | — |
| consec3 / pts30 | 3 | −25.98 | 10:40 |
| consec4 / pts40 | 8 | −27.17 | 12:33 |
| consec5 / pts45 | 9 | −31.44 | 12:51 |

**Every tight setting is worse than doing nothing on this day.** Today had 2 wins
and 11 losses, and both wins (+20 @ 10:40, +39 @ 14:28) were the *reversals that
ended the losing streaks* (running realized PnL bottomed at −47.5 just before the
14:28 win; max streak was 8). A loss-streak breaker halts *during* a streak, so
for a mean-reversion strategy it **systematically cuts the reversal wins that are
its edge**. To avoid touching today at all requires consec > 8 and points > 48 —
i.e. it only fires on a day *worse than* this −4.9% day.

Conclusion: today's churn was an entry-**quality** problem (addressed upstream by
the Setup D trend filter, PR #599), not a loss-**magnitude** problem. A tight
circuit breaker is the wrong tool for it.

## Decision — catastrophic-only

Fix the dead-breaker bug and keep the mechanism, but enable it at
**catastrophic-only** thresholds that sit above the 2026-07-07 day:

- `max_consecutive_losses: 10`
- `daily_loss_limit_points: 60`

These restore a tail-risk backstop (a truly disastrous futures day *can* now halt
trading) without fighting normal mean-reversion churn/reversals. Both are
env-overridable (`RISK_MAX_CONSECUTIVE_LOSSES`, `RISK_DAILY_LOSS_LIMIT_POINTS`).
Fail-safe: the breakers only ever *block* new entries — they cannot cause an
entry.

## Tests

`tests/shared/risk/test_circuit_breaker.py`: consecutive-loss block at threshold,
2-loss no-block, win resets streak, disabled-when-0, daily-points block, points
disabled-when-0, daily reset clears streak + unblocks, config defaults + from_dict
parsing. Existing risk suites unchanged (breakers default-disabled).

## Scope guard / follow-ups

- Entry-quality churn control: Setup D trend filter (PR #599, separate).
- RC4 (re-entry cooldown) and RC3 (opening-auction spread guard) remain separate.
- A margin-based futures capital model (to make the KRW %-path meaningful) is out
  of scope; the points-native breaker sidesteps it.
