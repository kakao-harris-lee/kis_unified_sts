# bb_reversion_15m — paper validation runbook

## Status
PAPER-ONLY. `config/futures_live.yaml::futures_live.enabled` MUST stay
`false` and Redis `futures:live:suspended` set — enabling this strategy
only loads it into the paper orchestrator alongside Setup A/C. Live
activation remains behind Phase 5 Gate 1–3 + written operator approval
(docs/runbooks/phase5-verification.md) — OUT OF SCOPE here.

## What was validated
bb_reversion_15m passed the re-scoped robust gate
(reports/optuna/BB_REVERSION_15M_PROBE.md) AND its registered
production path reproduces that 15m-cadence strategy (T7 parity:
~466 trades / Sharpe 6.33 / PF 2.36 — 15m regime, NOT the 1m-cadence
~1584-trade failure). Backtest return/Sharpe MAGNITUDES are inflated by
a known futures P&L-accounting artifact — only the robustness/regime
transfers. **Paper is the real bar.**

## ⚠️ Accepted tradeoff — intra-15m stop-loss latency
The decision-cadence gate evaluates entry AND exit only once per closed
15m bar (required for parity — the strategy that passed the robust gate
only ever saw 15m bars). Consequence: stop-loss / exit conditions are
checked at most every 15 minutes; a -4% stop can overshoot intra-15m.
This is an INHERENT property of the validated strategy, operator-
accepted (2026-05-18). Independent safety nets remain: the engine/risk
layer + EOD. An intra-bar hard-stop is a documented FUTURE enhancement,
out of scope for parity. Monitor max adverse excursion in paper.

## Run
`sts trade start --asset futures --paper` — the TradingOrchestrator
loads all `enabled: true` futures strategies (bb_reversion_15m coexists
with Setup A/C). The live `StrategyManager` has the decision-cadence
gate wired (orchestrator `_init_indicator_engine` →
`set_indicator_engine`), so paper decisions occur at 15m cadence.

## Paper-validation GATE (operator decision; mirrors Phase 5 Gate-1, extended for thin sample)
bb_reversion_15m trades ~3/week on 15m → a 2-week window ≈ 6 trades,
statistically meaningless vs the ≥30–50-trade significance bar used by
the robust gate. Therefore:
- **Minimum:** ≥ 12 trading weeks AND ≥ 30 completed paper trades
  (target ≥ 50) before ANY verdict.
- **PASS (→ propose live Phase-5 Gate process):** over the window,
  net-of-cost paper Sharpe > 1.0 AND profit factor > 1.2 AND max
  drawdown within risk policy AND no week with a kill-switch/risk
  breach. Judged on the REALIZED paper distribution — NOT inflated
  backtest numbers.
- **FAIL / inconclusive:** below thresholds, or < 30 trades at 12
  weeks → do not advance; extend, retune (re-run the robust gate), or
  deprecate like the prior futures attempts.

## Monitoring
- Weekly: signal/fills monitor + Telegram FUTURES channel; confirm
  signals fire on CLOSED 15m bars only (look-ahead guard / C1).
- Track max adverse excursion per trade (intra-15m-stop exposure).
- Rollback: set `bb_reversion_15m.yaml::strategy.enabled: false` (no
  code change) — Setup A/C unaffected.
