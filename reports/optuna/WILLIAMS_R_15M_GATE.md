# williams_r_15m — re-scoped robust §6 gate verdict (2026-05-19)

Spec: docs/superpowers/specs/2026-05-19-futures-rlmppo-replacement-indicator-research-design.md §7
Tool: scripts/gate_futures_strategy.py (shared.backtest.robust_gate)
Data: data/kospi200f_1m_ch_101S6000.csv | holdout 2026-02-01 | min-trades 50 | 70 trials
Strategy: williams_r_15m (genuine 15m — timeframe_minutes:15, momentum_15m + mtf_base_15m)

## VERDICT: FAIL ❌ (terminal)

`>>> RE-SCOPED GATE: FAIL (a=False b=False c=False | median_sharpe=nan basin=0.0% n_valid=0)`

| Check | Requirement | Result | |
|---|---|---|---|
| (a) median valid trial (train) | Sharpe ≥ 0 & PF ≥ 1.0 | median_sharpe = **nan** (n_valid = **0**) | **FAIL** |
| (b) broad basin | ≥ 25% of valid trials clear (a) | **0.0%** (0 / 0 valid; 0 / 70 non-sentinel) | **FAIL** |
| (c) selected cfg OOS | Sh≥0,PF≥1,MDD≤25,ret≥0 | Sharpe **-15.22**, PF **0.00**, MDD **56.73%**, ret **-52.79%**, trades **6** | **FAIL** |

best train value: **-10.0000** (min-trades-floor sentinel — not a single trial cleared the ≥50-trade floor with non-catastrophic Sharpe)
best_params: `{'entry.params.oversold_threshold': -79.03755055240374, 'entry.params.reversal_threshold': -62.9484894284585, 'entry.params.overbought_threshold': -33.01141762445741, 'entry.params.williams_r_period': 18, 'entry.params.volume_threshold': 1.510897482634451, 'entry.params.confidence_reversal_scale': 22.787024763199863}`
Raw log: /tmp/wr15_gate.log (ephemeral)

## Decision

**Terminal for this candidate (spec §8).** `config/strategies/futures/williams_r_15m.yaml` stays `enabled: false` permanently; recorded as reproducible negative evidence (mirrors the RL_mppo 2026-05-15 / llm_directed_indicator 2026-05-17 arcs — code/config retained, not deleted).

All 70 Optuna trials are catastrophic or below the min-trades floor (n_valid = 0, basin = 0.0%) — strictly worse than the deprecated `llm_directed_indicator` (basin 12.5%). The genuine-15m timeframe axis on the **williams_r price-indicator family** is therefore **exhausted** for KOSPI200 futures. This empirically confirms the spec §2 informational-bottleneck thesis for this family.

**Spec §9 trigger fired:** "P1 yields zero survivors → Approach ③ (microstructure / cross-asset) — new spec." P2 (LLM-directed entry) is NOT triggered (it required a gate-surviving candidate; there is none). Next futures-signal work must start from *different information* (microstructure / cross-asset features), gated from scratch on the same robust §7 bar — not from re-tuning any price-indicator ensemble.

## Reproduce
```
cd <worktree> && python scripts/gate_futures_strategy.py \
  --strategy williams_r_15m --data data/kospi200f_1m_ch_101S6000.csv \
  --space config/optuna/futures/williams_r_15m.yaml \
  --holdout-split 2026-02-01 --min-trades 50 --trials 70
```
(TPESampler seed=42 — deterministic.)
