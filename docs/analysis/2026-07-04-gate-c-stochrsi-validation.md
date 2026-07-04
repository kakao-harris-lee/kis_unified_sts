# Gate C — StochRSI (`stochrsi_trend`) FUTURES Validation

- **Date:** 2026-07-04 (M2 indicator SoT handoff, Gate C)
- **Scope:** Paper-only R&D. Validation only — decide SHIP-TO-PAPER vs NO-SHIP for the
  `stochrsi_trend` FUTURES strategy. This is **not** the activation PR.
- **Symbol / window:** `101S6000`, minute bars, **2025-12-01 .. 2026-04-30** (the
  reliable futures-minute window per project memory; older/newer minute data degraded).
- **Worktree:** `/home/deploy/project/kis_wt/gate-c-stochrsi` (origin/main + throwaway wiring).
- **Verdict:** ⛔ **NO-SHIP.**

---

## 1. Setup — producer enablement (throwaway worktree wiring)

The strategy `stochrsi_trend` reads flat keys `stochrsi_k / stochrsi_d / stochrsi_k_prev`
(%K/%D crossover, bidirectional, oversold 20 / overbought 80; exit = `williams_r_exit`).
Two independent blockers had to be solved before the backtest was meaningful — **both
fixed in-worktree only, reported as a diff, not committed, not the activation PR:**

### Blocker 1 — producer gated OFF in the adapter
`shared/backtest/adapter.py` constructs `StreamingIndicatorEngine(...)` **without**
`stochrsi_enabled`/periods, so the config-gated StochRSI producer
(`shared.indicators.reference.StochRSICalculator`, wired into
`StreamingIndicatorEngine.get_indicators` → `services/trading/indicator_queries.py:90`)
stays OFF → keys read neutral 50 → strategy inert (0 signals).

### Blocker 2 — market_data / indicators split (backtest-vs-live parity gap)
`stochrsi_trend.generate()` reads **only** `context.market_data` (`entry/stochrsi_trend.py:59-63`),
but the adapter builds `EntryContext(market_data=bar, indicators=indicators)` — the stochrsi
keys land in `indicators`, invisible to a market_data-only reader. In **live** the
orchestrator does `enriched.update(indicators)` then `market_data=enriched`
(`services/trading/orchestrator.py:5085-5108`), so live puts the keys in market_data.
The backtest adapter did not mirror that. Fixed by merging `{**bar, **indicators}` into the
entry market_data — faithful to the live contract.

### Diff applied (worktree only, `shared/backtest/adapter.py`)
```diff
@@ __init__ (StreamingIndicatorEngine construction)
+        _stochrsi_cfg = (
+            strategy_config.get("strategy", {}).get("indicators", {}).get("stochrsi", {})
+            or {}
+        )
         self._indicator_engine = StreamingIndicatorEngine(
             bb_period=bb_period, bb_std=bb_std, rsi_period=rsi_period,
             mtf_timeframes=mtf_timeframes,
             mtf_warmth_timeframe=self._indicator_contract.warmth_timeframe,
+            stochrsi_enabled=True,
+            stochrsi_rsi_period=int(_stochrsi_cfg.get("rsi_period", 14)),
+            stochrsi_stoch_period=int(_stochrsi_cfg.get("stoch_period", 14)),
+            stochrsi_k_period=int(_stochrsi_cfg.get("k_period", 3)),
+            stochrsi_d_period=int(_stochrsi_cfg.get("d_period", 3)),
         )
@@ on_bar (EntryContext construction)
+        entry_market_data = {**bar, **indicators}
         context = EntryContext(
-            market_data=bar,
+            market_data=entry_market_data,
             indicators=indicators, current_positions=current_positions,
             timestamp=timestamp, metadata=metadata,
         )
```

> Activation (only if SHIP) requires a **separate PR** — config `enabled:true` +
> `indicators.stochrsi.enabled:true` + the *real* adapter/engine wiring — and must land
> **after Gate A (#561) merges**. Production config stays `enabled:false`; nothing was enabled.

### Producer sanity proof — keys are LIVE (not constant 50)
Drove Dec-2025 `101S6000` bars through the wired adapter and sampled the resolver output
per bar (`engine._stochrsi_enabled=True`, `min_bars=28`, periods 14/14/3/3):

| key | n | min | max | mean | stdev | unique vals | const-50? |
|-----|---|-----|-----|------|-------|-------------|-----------|
| `stochrsi_k`      | 7174 | 0.00 | 100.00 | 50.11 | 32.17 | 6102 | **False** |
| `stochrsi_d`      | 7174 | 0.00 | 100.00 | 50.11 | 30.77 | 6747 | **False** |
| `stochrsi_k_prev` | 7174 | 0.00 | 100.00 | 50.11 | 32.16 | 6103 | **False** |

- Oversold bars (`k<20`): **1750**; Overbought bars (`k>80`): **1781** → ample signal candidates.
- Strategy `context.market_data` saw `stochrsi_k` on **50 of last 50 bars** (merge confirmed).
- **Producer is confirmed live. The strategy is exercised, not inert.**

---

## 2. Full-sample backtest (Dec 2025 – Apr 2026)

`BacktestConfig.futures(point_value=50_000)`, slippage reflected (round-trip, both
directions; `engine.py:643-667`), `williams_r_exit`.

| Metric | Value |
|--------|-------|
| Trades | 1655 |
| Win rate | 54.4% |
| Profit factor | **0.79** |
| Sharpe (annualized) | **−2.67** |
| Max drawdown | 351.7% |
| Total return | **−328.2%** |
| Total PnL | **−32,822,798 KRW** |

**Win rate > 50% but PF < 1 and Sharpe deeply negative** → many small winners, few large
losers. The `williams_r_exit` (opposite-signal indicator flip, 120-min time-cut, −3% stop)
dominates exits: `signal=1567, stop_loss=49, time_cut=34, take_profit=4`. Winners are cut /
given back while losers run — a mean-reversion exit strapped onto a crossover entry.

### Long / short breakdown — **ASYMMETRIC (short side catastrophic)**

| Side | Trades | Win rate | PF | Total PnL | Avg PnL% | Avg hold |
|------|--------|----------|-----|-----------|----------|----------|
| LONG (BUY)  | 828 | 57.7% | 0.95 | −3,400,334 | +0.003% | 105 min |
| SHORT (SELL)| 827 | 51.0% | **0.65** | **−29,422,464** | **−0.096%** | 107 min |

The short side bleeds **8.6×** the long side and carries the loss. Longs are ~breakeven on a
per-trade basis (+0.003%/trade, below round-trip cost); shorts have a persistent negative
drift (−0.096%/trade). No stable directional edge on either side.

---

## 3. Walk-forward — 5 contiguous monthly OOS folds (each engine-run independently)

Fixed config params (no optimization); folds are out-of-sample temporal segments testing
robustness/stability. Per-fold:

| Fold | Trades | Sharpe | Return% | Win% | PF | PnL (KRW) | Long PnL | Short PnL |
|------|--------|--------|---------|------|-----|-----------|----------|-----------|
| 2025-12 | 301 | **−5.44** | −75.6 | 49.8 | 0.60 | −7,559,371 | −704,876 | −6,854,495 |
| 2026-01 | 341 | **−4.25** | −170.2 | 53.7 | 0.50 | −17,017,980 | −3,664,205 | −13,353,775 |
| 2026-02 | 294 | **−2.99** | −36.7 | 54.8 | 0.84 | −3,674,434 | +2,416,964 | −6,091,398 |
| 2026-03 | 386 | **−1.77** | −50.8 | 56.5 | 0.90 | −5,080,287 | −6,484,377 | +1,404,090 |
| 2026-04 | 329 | **+0.04** | +0.7 | 55.3 | 1.00 | +70,447 | +4,348,697 | −4,278,250 |

- **Return-positive folds: 1/5. Sharpe-positive folds: 1/5** — and the single "positive" fold
  (Apr) is **+0.7% return / Sharpe +0.038 / PF 1.00** — statistically indistinguishable from
  zero (breakeven, not an edge).
- 4/5 folds negative, catastrophically so early (Dec/Jan Sharpe −5.4 / −4.2).
- The Dec→Apr improvement is monotonic but only *reaches* breakeven; it never establishes a
  positive edge.
- **Long/short sign is unstable across folds** — the profitable side flips (Feb long +, short −;
  Mar short +, long −; Apr long +, short −). No side holds a durable edge; this is regime noise,
  not a symmetric tradable signal.

---

## 4. Verdict — ⛔ NO-SHIP

`stochrsi_trend` on intraday `101S6000` is **not shippable to paper.** It fails every SHIP
criterion:

1. **Walk-forward collapse** — 4/5 OOS folds negative (aggregate Sharpe −2.67, PF 0.79); the
   lone non-negative fold is breakeven (+0.038 Sharpe). Robust-negative, not marginal.
2. **Long/short asymmetry** — full-sample shorts lose 8.6× longs; per-side profitability flips
   fold-to-fold. No symmetric edge, violating the futures long/short-symmetry requirement.
3. **No edge net of costs** — win rate 54% but PF 0.79; long per-trade return ≈ 0 (below
   round-trip cost), short per-trade return −0.096%. Costs + the mean-reversion `williams_r_exit`
   (winners cut / losers run) dominate.

This is exactly the outcome the prior predicted: intraday KOSPI200 futures are mean-reverting,
and **every trend/momentum entry tried — `macd_ema`, `williams_r` (trend), `momentum`, ORB
trend-day, CTA swing, conviction-hold — has failed walk-forward; only mean-reversion survives
(Setup A/C/D).** A StochRSI %K/%D crossover-trend entry joins that list. Optimization would not
rescue it — a Sharpe −2.67 / PF 0.79 / 4-of-5-negative surface is robust-negative, and per prior
gates, tightening trend gates makes OOS worse, not better.

### Recommendation
- **Do NOT activate** `stochrsi_trend` for futures. Keep `enabled:false`. No activation PR.
- If a StochRSI signal is ever revisited for futures, treat it as a **mean-reversion context
  modifier** for Setup A/C/D (e.g. oversold/overbought confirmation on the reversion side),
  **not** a standalone crossover-trend entry — mirroring the standing recommendation from the
  ORB/CTA/conviction gates.
- The throwaway adapter wiring (Blockers 1 & 2) is a real backtest-vs-live parity finding: the
  production adapter neither enables the producer nor mirrors the orchestrator's
  `enriched.update(indicators)` merge. Any future market_data-reading indicator strategy will be
  silently inert in backtest until both are addressed in the eventual activation PR.

---

## Reproduction
- Sanity: `scratchpad/gate_c_sanity.py` — producer liveness + market_data merge proof.
- Backtest/WF: `scratchpad/gate_c_backtest.py` → `scratchpad/gate_c_results.json`.
- Run pattern: `cd /home/deploy/project/kis_wt/gate-c-stochrsi && PYTHONPATH=/home/deploy/project/kis_wt/gate-c-stochrsi /home/deploy/project/kis_unified_sts/.venv/bin/python <script>`
- Adapter loaded from worktree: `/home/deploy/project/kis_wt/gate-c-stochrsi/shared/backtest/adapter.py` (verified via `inspect.getsourcefile`).
