# Gate A (RSI) — Streaming RSI Wilder Convergence Backtest

**Date:** 2026-07-04
**Gate:** M2 indicator SoT handoff — Gate A (RSI)
**Change under test:** `services/trading/indicator_calculations.py::IndicatorCalculationMixin._calc_rsi`
rolling-SMA-of-gains/losses → **Wilder EMA** (alpha=1/period, adjust=False, first-delta
seed, full-series).
**Branch:** `feat/indicator-rsi-wilder-gated` (candidate `feb18875`) vs `origin/main` (baseline `7ed66a42`)
**Scope:** paper-only R&D validation — no live trading impact.

## VERDICT: **PASS**

Converging the streaming RSI from rolling-SMA to Wilder smoothing causes **no meaningful
degradation** across the RSI-consuming stock strategy set. The change alters backtest
behavior for exactly **one** strategy (`bb_reversion`), and there it is **neutral-to-favorable**
on every risk-adjusted metric (Sharpe/MDD/PnL/win-rate) with only a marginal Profit-Factor
slip (−0.05) inside an already-losing (PF < 1) strategy. Every other RSI-consuming strategy
is **bit-identical** baseline vs candidate. Recommended next step: merge
`feat/indicator-rsi-wilder-gated` → `main` via PR + review.

---

## Change isolation (verified)

`git diff 7ed66a42 feb18875` touches only two files: `_calc_rsi` (production) and
`tests/unit/indicators/test_calc_parity.py` (test). No other production code differs.
`_calc_rsi` produces the streaming **`rsi`** indicator key (period 14) via
`indicator_queries.py`, which the backtest exercises through
`shared/backtest/adapter.py::BacktestStrategyAdapter → StreamingIndicatorEngine`.

Two RSI computation paths are **NOT** touched by this change and are therefore unaffected by
construction (empirically confirmed — see control):
- **Daily-strategy RSI**: `DailyBacktestAdapter._compute_rsi` + `calculate_all_momentum`
  (`shared/indicators/momentum.py::RSICalculator`, already Wilder) → produces `rsi`,
  `daily_rsi_5`, `daily_rsi_14` for daily strategies. Never calls `_calc_rsi`.
- **`vr_composite` RSI**: its entry/exit use `VolumeRatioCalculator.calculate_rsi` (own impl).

Provenance was verified per-run via `inspect.getsource(_calc_rsi)`: baseline runs report
`rsi=SMA_ROLLING`, candidate runs report `rsi=WILDER`, each resolving to its own worktree's
`indicator_calculations.py` (PYTHONPATH precedence confirmed correct).

## Universe & period

| Set | Symbols | Period | Notes |
|-----|---------|--------|-------|
| Minute strategies | 73 minute-data symbols (equal-weight portfolio; per-symbol runs aggregated) | 2026-03-01 → 2026-06-30 | Full minute universe. `trend_pullback` used a 15 large-cap subset (see drops). |
| Daily control (`vr_composite`) | 533-symbol universe, 68 traded | 2024-01-01 → 2026-06-30 | Multi-year daily window. |

Capital/sizing mirror the CLI (`initial_capital`, `position_size_pct`, `max_positions`,
`order_amount_per_stock` from each strategy's config). Aggregation is the project convention:
per-symbol backtests, then equal-weight portfolio + trade-weighted aggregates (win-rate =
Σwins/Σtrades; PF = Σgross_win/Σgross_loss). No multi-symbol concatenation into one series.

## RSI-dependence map (grep + code trace, both worktrees)

| Strategy | Reads which RSI | Adapter | Affected by `_calc_rsi`? |
|----------|-----------------|---------|--------------------------|
| **bb_reversion** (`mean_reversion` entry) | streaming `rsi` | minute | **YES** |
| **trend_pullback** | streaming `rsi` (gated behind `sma_200`) | minute | reachable only if `sma_200` warms (it can't here) |
| **momentum_breakout** | streaming `rsi` (`_trend_filter`) + `daily_rsi_5` | minute | streaming read present but non-binding |
| **trix_golden** | `df["rsi"]` in exit | minute (5m) | exit `rsi` column dormant in backtest |
| **vr_composite** | own `VolumeRatioCalculator.calculate_rsi` | daily | No (control) |
| technical_consensus / technical_consensus_exit_experiment | `daily_rsi_14` (alias) | daily | No (daily path) |
| pattern_pullback | `rsi5`→`daily_rsi_5` | daily | No (daily path) |
| daily_pullback | `daily_pullback` daily RSI | daily | No (daily path) |
| trend_continuation_vwap | `daily_rsi_5` | minute | No (daily_rsi key, not `_calc_rsi`) |
| llm_adaptive_sizing_example | streaming `rsi` (`mean_reversion`) | minute | same class as bb_reversion (example config, not separately run) |

The five daily / daily-`rsi` strategies never touch `_calc_rsi`; the `vr_composite` daily
control (below) empirically proves that entire path is untouched (bit-identical). They are
therefore excluded from the run matrix as guaranteed 0-delta.

## Results — baseline (SMA) → candidate (Wilder)

Metrics: `trades` = total; `WR%` = trade-weighted win-rate; `PF` = aggregate profit factor
(Σgross_win/Σgross_loss); `ewSharpe`/`ewMDD` = equal-weight mean of per-symbol Sharpe/MDD;
`net` = Σ realized PnL (KRW).

| Strategy | flavor | traded syms | trades | WR% | PF | ewSharpe | ewMDD | net PnL | per-symbol identical? |
|----------|--------|-------------|--------|-----|-----|----------|-------|---------|-----------------------|
| **bb_reversion** | SMA→WIL | 52→54 | **617→413** | 40.52→40.92 | 0.444→0.395 | −4.03→−1.21 | 0.344→0.262 | −969,443→−766,241 | **No (moves)** |
| momentum_breakout | SMA→WIL | 52→52 | 348→348 | 26.1→26.1 | 0.795→0.795 | −16.66→−16.66 | 0.586→0.586 | −512,465→−512,465 | Yes (Δ=0) |
| trix_golden | SMA→WIL | 42→42 | 140→140 | 25.7→25.7 | 0.388→0.388 | −10.68→−10.68 | 0.196→0.196 | −366,055→−366,055 | Yes (Δ=0) |
| trend_pullback¹ | SMA→WIL | 0→0 | 0→0 | — | — | — | — | 0→0 | Yes (0 trades) |
| **vr_composite** (daily control) | SMA→WIL | 68→68 | 374→374 | 46.0→46.0 | 2.321→2.321 | −0.754→−0.754 | 0.200→0.200 | +15,513,496→+15,513,496 | Yes (Δ=0) |

¹ `trend_pullback` on the 15 large-cap subset (`005930,000660,005380,005490,035420,035720,051910,006400,000270,105560,055550,012330,066570,003550,034730`).

### bb_reversion per-metric delta (the only mover)

| Metric | baseline | candidate | Δ |
|--------|----------|-----------|---|
| trades | 617 | 413 | **−204 (−33%)** |
| win-rate % | 40.52 | 40.92 | **+0.40** |
| profit factor | 0.4443 | 0.3947 | **−0.0496** |
| ewSharpe | −4.029 | −1.210 | **+2.819 (better)** |
| twSharpe | −6.232 | −5.711 | **+0.522 (better)** |
| ewMDD | 0.3436 | 0.2615 | **−0.082 (better)** |
| ewReturn % | −0.213 | −0.159 | +0.054 (better) |
| net PnL | −969,443 | −766,241 | **+203,202 (less loss)** |

The trade-count reduction is **broad-based**, not a single-symbol artifact: 51 of 73 symbols
change trade count (Wilder RSI is smoother → fewer sub-threshold oversold crossings of the
`rsi_oversold=35` gate). Per-symbol Sharpe is balanced — 26 improved / 21 regressed / 26 flat
— i.e. no systematic directional harm; the drift is noise-like at the symbol level while the
aggregate risk metrics tighten.

### Aggregate across the RSI-consuming minute set (bb_reversion + momentum_breakout + trix_golden + trend_pullback)

| | trades | WR% | PF | net PnL |
|--|--------|-----|-----|---------|
| BASELINE | 1105 | 34.12 | 0.6179 | −1,847,963 |
| CANDIDATE | 901 | 32.85 | 0.6225 | −1,644,761 |
| Δ | −204 | −1.27pp | **+0.0046** | **+203,202 (less loss)** |

The aggregate PF is marginally **better** and aggregate net PnL is **less negative**. The
aggregate WR −1.27pp is a pure **composition artifact**: all trade-count movement is in
`bb_reversion` (the higher-WR ~40% member), so as it sheds trades the mix tilts toward the
fixed-count lower-WR members (momentum 26%, trix 26%). Every individual strategy's own
win-rate is flat or up.

## Interpretation

- **Only `bb_reversion` is materially exercised by the RSI change.** momentum_breakout and
  trix_golden read `rsi`/`df["rsi"]` in code, but those reads are non-binding (momentum's
  `_trend_filter rsi>=40` gate never flips a decision here) or dormant (trix's exit `rsi`
  column is not populated in the backtest exit frame) → bit-identical output.
- **`bb_reversion` does not degrade.** Fewer trades (smoother Wilder RSI), but Sharpe, MDD,
  PnL and win-rate all move neutral-to-favorable. The lone adverse metric is PF (−0.05), and
  it sits inside a strategy that loses money in **both** regimes (PF ≪ 1). `bb_reversion` is a
  disabled/observation strategy in production; the change slightly reduces its bleed rather
  than worsening a profitable edge.
- The handoff criterion — *"Sharpe/MDD/win/PF 유의미 악화 없으면 통과"* — is satisfied: no
  meaningful degradation; the single behavioral change (trade-frequency reduction) comes with
  improved risk-adjusted metrics.

## Symbols / ranges dropped (and why)

- **`trend_pullback` — not exercisable on this data; run on a 15-symbol subset only.**
  Its entry returns `None` whenever `sma_200 <= 0` (`entry/trend_pullback.py:154-157`), and
  the `rsi` read (line 211) is downstream of that gate. `sma_200` needs 200 daily bars, but
  the minute-only window is ~4 months (~80 sessions) and the adapter's daily-close deque is
  `maxlen=20` → `sma_200` never warms → **0 trades in both branches**. Its RSI gate is
  therefore unreachable in a minute-only backtest; result is Δ=0 by non-exercise, not by
  demonstrated safety. (The full-73 run was abandoned — >19 min CPU with no entries and reaped
  by background cleanup; the 15-symbol foreground confirm returned 0 trades on both branches.)
- **Minute strategies confined to 2026-03..06 / 73 symbols** — the only span with stock
  minute Parquet coverage. Daily strategies (`vr_composite` control) used 2024-01..2026-06.
- **Daily / daily-`rsi` strategies not run** (technical_consensus, technical_consensus_exit_experiment,
  pattern_pullback, daily_pullback, trend_continuation_vwap): they consume `daily_rsi_*` /
  `VolumeRatioCalculator` RSI, never `_calc_rsi`. The `vr_composite` daily control (bit-identical,
  incl. per-symbol) empirically proves the daily-adapter RSI path is untouched, so these are
  guaranteed 0-delta.

## Method / reproducibility

Per-symbol `BacktestStrategyAdapter`/`DailyBacktestAdapter` + `BacktestEngine` driven by a
throwaway harness (scratchpad) that mirrors the CLI's config construction and captures
`BacktestResult` fields incl. trade-level `pnl` for aggregate PF / win-rate. Baseline and
candidate ran on the **same** symbols, dates, and capital, differing only by worktree
(`/home/deploy/project/kis_wt/baseline-main` vs `/home/deploy/project/kis_wt/gate-a-rsi`) with
matching `PYTHONPATH`. RSI flavor asserted per run.

## Recommendation

**PASS** — safe to merge. Proceed to merge `feat/indicator-rsi-wilder-gated` → `main` via
PR + code review. The Wilder streaming RSI now matches the M1-certified shared
`RSICalculator` / daily path (parity is the point of the change) with no risk-adjusted
regression in any RSI-consuming stock strategy.

**Follow-up (non-blocking):** `trend_pullback`'s streaming-`rsi` gate could not be evaluated
here (blocked upstream by `sma_200` warmup). If future validation wants it exercised, seed the
backtest with ≥200 daily bars of context (daily+minute join) so the `sma_200` gate opens.
