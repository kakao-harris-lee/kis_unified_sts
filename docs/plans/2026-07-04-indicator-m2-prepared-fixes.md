# Indicator M2 — Prepared Fixes for Contended Files (UNAPPLIED)

Status: PREPARED, NOT APPLIED. Date: 2026-07-04. Branch context:
`feat/indicator-catalog-m1` (M2 branch A).

## Why this document exists

M2 branch A ships an additive, conflict-free reference layer only
(`shared/indicators/reference.py` + `tests/unit/indicators/test_reference.py`).
The three defects below live in files currently being edited by the unmerged
branches `refactor/lizard-top5` and `dashboard-routes-split`:

- `services/trading/indicator_calculations.py`
- `services/trading/indicator_queries.py`
- `shared/regime/adaptive_detector.py`
- `tests/unit/indicators/test_calc_parity.py` (snapshot owner)

Editing them now would collide. This document specifies the exact diffs to apply
**after** those branches merge, each with a rationale and a required verification
gate. The reference layer is the delegation target for all three.

## Confirmed defects (post-merge code, read-only verification)

| # | Location | Current behavior | Standard | Numeric delta (64-bar deterministic sample) |
|---|----------|------------------|----------|--------------------------------------------|
| 1 RSI | `indicator_calculations.py:26-47 _calc_rsi` | rolling-SMA of gains/losses (`avg_gain = sum(gains)/len(gains)`) | Wilder EMA (`alpha=1/period`) — only `momentum.RSICalculator` is industry-standard (M1 pandas-ta certified) | runtime **60.198576** vs shared Wilder **47.099143**, delta **13.10** |
| 2 ADX | `adaptive_detector.py:389-432 _calc_adx` | named ADX, returns a single last-bar **DX**: no directional-movement rule (`np.maximum(H-Hp,0)` never zeroes the smaller move), **SMA**-smoothed DI (`rolling(period).mean()`), and **no** final DX→ADX Wilder smoothing (`return float(dx)`) | Wilder-smoothed ADX (runtime `indicator_calculations._calc_adx` is already correct) | detector **15.873272** vs canonical Wilder ADX **31.6** (reference) / **31.72** (runtime), delta **~15.8** |
| 3 StochRSI | `stochrsi_trend.py:55,61-63` consumes `stochrsi_k/d/k_prev`; **no producer** anywhere (`get_indicators`, `get_momentum_indicators` never emit them) | a producer must exist | consumer always reads `data.get(..., 50)` → crossover `k>d and k_prev<d` = `50>50` = **always False** → strategy is **inert** |
| 4 Bollinger | `indicator_calculations.py:12-24 _calc_bb` | sample std (`ddof=1`, `/(n-1)`) | library default is population std (`ddof=0`) | ddof=1 lower/upper **99.902454 / 114.519124** vs ddof=0 **100.087505 / 114.334073** |

Defect 4 (Bollinger) is a *convention*, not a bug — the repo deliberately uses
`ddof=1` to match Polars `rolling_std`. The reference layer makes `ddof` explicit
(`BollingerBandsCalculator(ddof=...)`) and defaults to the repo convention, so no
runtime change is required; it is listed for completeness and to document the
convention for future third-party comparisons.

All deltas above are reproduced deterministically by
`tests/unit/indicators/test_calc_parity.py` and cross-checked by
`tests/unit/indicators/test_reference.py` on the identical RNG-free OHLCV sample.

---

## Diff 1 — `_calc_rsi` → Wilder (converge to the shared standard)

File: `services/trading/indicator_calculations.py`

Why: M1 established `momentum.RSICalculator` (Wilder EMA) as the single
industry-standard RSI (certified against pandas-ta). The streaming `_calc_rsi`
uses a rolling-SMA that materially diverges (delta 13.1 on the reference sample),
so the streaming `bb_reversion` / `mean_reversion` / RSI filters see a different
oversold/overbought line than the batch/backtest path. Converging removes that
schema/value split.

The streaming helper is deliberately numpy-free (hot path). To keep it
dependency-light AND hit exact parity with `momentum.RSICalculator` — which uses
`ewm(alpha=1/period, adjust=False)`, i.e. a first-delta-seeded Wilder EMA (not an
SMA seed) — port that exact recursion in pure Python:

```diff
     def _calc_rsi(self, closes: list[float]) -> float:
-        """RSI using rolling SMA of gains/losses (matching core/indicator_engine.py)."""
+        """RSI using Wilder smoothing (alpha=1/period), matching the
+        M1-certified shared RSICalculator (ewm adjust=False, first-delta seed)."""
         if len(closes) < self.rsi_period + 1:
             return 50.0
-
-        # Use the last rsi_period+1 closes to get rsi_period deltas
-        recent = closes[-(self.rsi_period + 1) :]
-        gains = []
-        losses = []
-        for i in range(1, len(recent)):
-            delta = recent[i] - recent[i - 1]
-            gains.append(delta if delta > 0 else 0.0)
-            losses.append(-delta if delta < 0 else 0.0)
-
-        avg_gain = sum(gains) / len(gains)
-        avg_loss = sum(losses) / len(losses)
-
-        if avg_loss == 0:
-            return 100.0
-
-        rs = avg_gain / avg_loss
-        return 100.0 - (100.0 / (1.0 + rs))
+        period = self.rsi_period
+        alpha = 1.0 / period
+        one_minus = 1.0 - alpha
+        # Seed on the first delta, then Wilder-EMA over the FULL series
+        # (adjust=False semantics) — do NOT window to the last period+1 closes,
+        # or the exponential warmup is lost and parity breaks.
+        avg_gain = 0.0
+        avg_loss = 0.0
+        seeded = False
+        for i in range(1, len(closes)):
+            delta = closes[i] - closes[i - 1]
+            gain = delta if delta > 0.0 else 0.0
+            loss = -delta if delta < 0.0 else 0.0
+            if not seeded:
+                avg_gain, avg_loss, seeded = gain, loss, True
+            else:
+                avg_gain = alpha * gain + one_minus * avg_gain
+                avg_loss = alpha * loss + one_minus * avg_loss
+        if avg_loss == 0.0:
+            return 100.0 if avg_gain > 0.0 else 50.0
+        rs = avg_gain / avg_loss
+        return 100.0 - 100.0 / (1.0 + rs)
```

Note: `get_indicator_features` (line 231) and `get_indicators_tf` (line 464) both
call `_calc_rsi`, so this single change fixes every streaming RSI consumer.

Verification gate (BLOCKING):
1. Parity: update `test_calc_parity.py` — the `_RSI_RUNTIME_SMA=60.198576`
   snapshot and `test_rsi_two_paths_diverge_materially` (delta floor > 5.0) fail
   **by design** (the two paths converge). Replace with an equality assertion
   `runtime ≈ shared within 1e-6` and set the shared snapshot 47.099143.
2. Backtest: RSI value shift changes entry/exit timing for `bb_reversion`,
   `mean_reversion`, and any RSI-filtered strategy. Run the stock + futures
   backtest suite and diff Sharpe / MDD / win-rate / PF before promoting. This is
   a value change, not a refactor — treat as a strategy change.

---

## Diff 2 — `adaptive_detector._calc_adx` → delegate to `reference.ADXCalculator`

File: `shared/regime/adaptive_detector.py`

Why: the detector's `_calc_adx` under-reports trend strength by roughly half
(15.9 vs the correct 31.6 on the reference sample) because it (a) drops the
directional-movement rule, (b) uses SMA-smoothed DI, and (c) omits the final
DX→ADX smoothing entirely — it returns a single DX. Any regime gate keyed on an
ADX trend threshold is mis-triggering.

Delegate to the canonical implementation instead of maintaining a third ADX:

```diff
+from shared.indicators.reference import ADXCalculator
+
     def _calc_adx(
         self,
         high: np.ndarray,
         low: np.ndarray,
         close: np.ndarray,
         period: int = 14
     ) -> float:
-        """Calculate Average Directional Index. ..."""
-        if len(high) < period + 1:
-            return 0.0
-
-        # Calculate directional movement
-        plus_dm = np.maximum(high[1:] - high[:-1], 0)
-        minus_dm = np.maximum(low[:-1] - low[1:], 0)
-        ...
-        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) != 0 else 0
-        return float(dx)
+        """Average Directional Index — canonical Wilder ADX.
+
+        Delegates to shared.indicators.reference.ADXCalculator so the regime
+        detector, the runtime engine, and the reference layer share one ADX.
+        """
+        adx = ADXCalculator(period=period).calculate_last(high, low, close)
+        return float(adx) if adx is not None else 0.0
```

`calculate_last` preserves the current non-None `float` return contract
(returns 0.0 when there is insufficient data, matching the old early return).

Verification gate (BLOCKING):
1. Parity: `test_calc_parity.py::test_adx_two_implementations_diverge`
   (`_ADX_DETECTOR_DX=15.873272`, delta floor > 5.0) fails **by design**. Update
   the detector snapshot to the Wilder value (~31.6) and convert the divergence
   assertion into a "detector == reference within warmup tolerance (~0.1)"
   agreement check.
2. Regime characterization: ADX ~doubling shifts `AdaptiveRegimeDetector`'s
   trend/range vote. Re-run the HAR-RV / regime-gate head-to-head and the
   counterfactual EOD-proxy PnL (regime-gate-analyst) before promoting — the gate
   admits/blocks a different set of signals now.

Note the small (~0.08) warmup-seed offset between reference `calculate_last`
(31.63) and the runtime `_calc_adx` (31.72): both are canonical Wilder ADX; they
differ only in whether the first DI is reported at the seed bar or one bar later.
This is immaterial next to the 15.8-point defect being fixed. A later pass may
also delegate the runtime `_calc_adx` to the reference for a true single source.

---

## Diff 3 — Expose StochRSI at runtime (wire the missing producer)

Files: `services/trading/indicator_queries.py` (+ config, + optional Redis state)

Why: `StochRSITrendEntry` is registered and consumes `stochrsi_k`,
`stochrsi_d`, `stochrsi_k_prev`, but nothing produces them, so the strategy is
inert (always neutral 50). `reference.StochRSICalculator` is the producer and its
`latest_values(df)` emits exactly those three flat keys.

### 3a. Config (No-Hardcoding)

Add `config/strategies/futures/stochrsi_trend.yaml` params (already matched to the
strategy's `StochRSIConfig` defaults):

```yaml
indicators:
  stochrsi:
    rsi_period: 14
    stoch_period: 14
    k_period: 3
    d_period: 3
```

### 3b. Producer wiring in `get_indicators`

`get_indicators` (indicator_queries.py:18-147) already has the closed-candle
`closes` list (line 69) built from `acc.candles` — closed candles only, so this
is **look-ahead safe (C1)**: never read the in-progress buffer. Emit the three
keys:

```diff
+import pandas as pd
+from shared.indicators.reference import StochRSICalculator
+
         bb_lower, bb_middle, bb_upper = self._calc_bb(closes)
         rsi = self._calc_rsi(closes)
 
         result: dict[str, float] = {
             "bb_lower": bb_lower,
             "bb_middle": bb_middle,
             "bb_upper": bb_upper,
             "rsi": rsi,
         }
+
+        # StochRSI producer (flat keys consumed by StochRSITrendEntry).
+        # Params from config; latest_values() falls back to neutral 50 during
+        # warmup, preserving today's default behavior until enough bars exist.
+        if len(closes) >= self._stochrsi_min_bars:  # rsi_period + stoch_period
+            sr = StochRSICalculator(
+                rsi_period=self._stochrsi_rsi_period,
+                stoch_period=self._stochrsi_stoch_period,
+                k_period=self._stochrsi_k_period,
+                d_period=self._stochrsi_d_period,
+            ).latest_values(pd.DataFrame({"close": closes}))
+            result["stochrsi_k"] = sr["stochrsi_k"]
+            result["stochrsi_d"] = sr["stochrsi_d"]
+            result["stochrsi_k_prev"] = sr["stochrsi_k_prev"]
```

`latest_values` already derives `stochrsi_k_prev` as the **previous bar's %K**
from the same closed series — exactly the crossover input the strategy needs — so
no external state is strictly required.

### 3c. prev-K state (Redis TTL) — only if decision cadence ≠ bar cadence

`get_indicators` is cached per completed candle (line 60-64), so within one bar it
returns a stable `stochrsi_k_prev` (prior bar). If a future decoupling makes the
decision loop poll faster than the bar close and the strategy must compare against
the **previous decision cycle's** K (not the previous bar), persist it in Redis
DB 1 with a TTL (CLAUDE.md: new keys need a TTL; 24h operational default):

```
key:  futures:indicator:stochrsi_kprev:{symbol}
value: last-emitted stochrsi_k
TTL:   86400  # 24h operational default
```

Read this back as `stochrsi_k_prev` before overwriting with the current K. Prefer
3b (stateless, series-derived) unless cadence forces 3c — it avoids per-tick Redis
churn and is trivially look-ahead safe.

### 3d. Perf note

`get_indicators` is intentionally numpy/pandas-free for the hot path. 3b adds a
small `pd.DataFrame` build per candle (cached, so once per bar, not per tick). If
profiling flags it, port `StochRSICalculator` to a pure-Python variant mirroring
the numpy-free `_calc_rsi`/`_calc_stochastic` already in
`indicator_calculations.py` — the reference class stays the batch/backtest SoT.

Verification gate (BLOCKING):
1. Unit: a `stochrsi_trend` generator test that feeds a rising-then-crossing
   series and asserts a non-None BUY/SELL signal — proving the strategy is no
   longer inert (it currently can never fire).
2. Regression: `test_calc_parity.py` and existing `get_indicators` tests must
   still pass (additive keys only; no existing key changes).
3. Backtest → regime-gate → counterfactual before paper promotion (new signal
   source), per the strategy-lab pipeline.

---

## Cross-cutting: parity snapshot ownership

Diffs 1 and 2 intentionally break the "known divergence" snapshots in
`test_calc_parity.py` (that harness's stated purpose: fail loudly on
consolidation so the integrator updates constants consciously). Whoever applies
these diffs owns updating those constants in the same commit and flipping the
`diverge_materially` / `diverge` assertions into agreement assertions. The
reference snapshots in `test_reference.py` do not change.

## Apply order

1. Land `refactor/lizard-top5` + `dashboard-routes-split`.
2. Apply Diff 2 (ADX, lowest blast radius: one delegation) → regime gate.
3. Apply Diff 3 (StochRSI, additive) → new strategy path.
4. Apply Diff 1 (RSI, widest blast radius: touches every RSI consumer) →
   full backtest gate.
5. Update `test_calc_parity.py` snapshots in the same commits.
```
