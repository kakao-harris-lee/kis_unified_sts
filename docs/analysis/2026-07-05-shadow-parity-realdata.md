# Real-data shadow parity — engine vs legacy `_calc_*`

Engine (TA-Lib / NumPy) vs streaming `IndicatorCalculationMixin._calc_*` measured on identical bounded windows (runtime `candle_maxlen`) across real Parquet minute bars. `rel` = |engine − legacy| / |legacy|; `n` is the count of finite-rel comparisons (windows where legacy ~= 0 are excluded from the rel stats). **Classification is on the robust median** — a genuine convention change (Wilder vs SMA, ddof, fast vs slow) is present on ~every window, so it moves the median; a divergence confined to a minority tail (`≥50% div` column) is a degenerate-window artifact, not a value change. **delegate-safe** = median rel ≤ 1% (no backtest gate); **gate-required** = systematic value change, needs a Setup-A/C / bb_reversion / stochastic backtest gate before delegation.

## stock — 73 symbols, 975,677 bars, window=30, 40 samples/symbol

| indicator | n | median rel | p95 rel | p99 rel | max rel | ≥50% div | prior | classification |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `rsi` | 2,920 | 9.909% | 45.340% | 100.000% | 206.418% | 4.212% | safe | **gate-required** ⚠️ |
| `adx` | 2,837 | 2.005% | 14.027% | 28.836% | 86.224% | 0.211% | safe | **gate-required** ⚠️ |
| `atr` | 2,852 | 6.321% | 27.132% | 46.147% | 266.447% | 0.736% | gate | **gate-required** |
| `bb_middle` | 2,920 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |
| `bb_width` | 2,835 | 2.532% | 2.532% | 2.532% | 2.532% | 0.000% | gate | **gate-required** |
| `stoch_k` | 2,638 | 16.667% | 91.667% | 241.527% | 69655.556% | 14.215% | gate | **gate-required** |
| `mfi` | 2,914 | 0.000% | 0.000% | 100.000% | 100.000% | 2.951% | safe | **delegate-safe** |
| `rvol` | 2,920 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |

## stock — 73 symbols, 975,677 bars, window=240, 40 samples/symbol

| indicator | n | median rel | p95 rel | p99 rel | max rel | ≥50% div | prior | classification |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `rsi` | 2,920 | 0.000% | 0.000% | 100.000% | 100.000% | 1.062% | safe | **delegate-safe** |
| `adx` | 2,889 | 0.000% | 0.000% | 0.029% | 86.224% | 0.069% | safe | **delegate-safe** |
| `atr` | 2,856 | 6.332% | 24.248% | 38.019% | 11659.675% | 0.490% | gate | **gate-required** |
| `bb_middle` | 2,920 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |
| `bb_width` | 2,840 | 2.532% | 2.532% | 2.532% | 2.532% | 0.000% | gate | **gate-required** |
| `stoch_k` | 2,620 | 16.667% | 91.750% | 231.552% | 67988.889% | 14.313% | gate | **gate-required** |
| `mfi` | 2,916 | 0.000% | 0.000% | 100.000% | 100.000% | 2.846% | safe | **delegate-safe** |
| `rvol` | 2,920 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |

## futures — 17 symbols, 287,471 bars, window=30, 40 samples/symbol

| indicator | n | median rel | p95 rel | p99 rel | max rel | ≥50% div | prior | classification |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `rsi` | 680 | 8.885% | 32.014% | 53.771% | 151.173% | 1.176% | safe | **gate-required** ⚠️ |
| `adx` | 680 | 2.369% | 13.956% | 23.965% | 44.121% | 0.000% | safe | **gate-required** ⚠️ |
| `atr` | 680 | 8.797% | 51.066% | 272.554% | 1573.675% | 5.147% | gate | **gate-required** |
| `bb_middle` | 680 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |
| `bb_width` | 680 | 2.532% | 2.532% | 2.532% | 2.532% | 0.000% | gate | **gate-required** |
| `stoch_k` | 637 | 24.159% | 570.756% | 7109.652% | 73238.838% | 27.316% | gate | **gate-required** |
| `mfi` | 680 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |
| `rvol` | 678 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |

## futures — 16 symbols, 287,318 bars, window=240, 40 samples/symbol

| indicator | n | median rel | p95 rel | p99 rel | max rel | ≥50% div | prior | classification |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `rsi` | 640 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |
| `adx` | 640 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |
| `atr` | 640 | 8.865% | 56.689% | 274.530% | 573.701% | 6.250% | gate | **gate-required** |
| `bb_middle` | 640 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |
| `bb_width` | 640 | 2.532% | 2.532% | 2.532% | 2.532% | 0.000% | gate | **gate-required** |
| `stoch_k` | 604 | 22.221% | 449.528% | 4395.104% | 16711.356% | 25.166% | gate | **gate-required** |
| `mfi` | 639 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |
| `rvol` | 639 | 0.000% | 0.000% | 0.000% | 0.000% | 0.000% | safe | **delegate-safe** |

## Interpretation → Phase 2 delegation

Windows tested: 30, 240 bars. **Classified by the shortest window** — the runtime fires `get_indicators` from `len ≥ bb_period` (20), so early-session parity is what a live delegation must hold.

**Delegate-safe at every window (drop-in, no gate):** `bb_middle`, `mfi`, `rvol`. Only these are bit-identical to the legacy streaming calc across the runtime's variable window lengths.

**⚠️ Warmup-sensitive (safe ONLY at long windows — NOT drop-in):** `rsi`, `adx`. Bit-parity at ~200+ bars but divergent on the short windows the runtime uses early in a session. Classifying these off a single long window (as the first cut of this report did) is misleading — they are **gated value changes**, not free swaps.

**Gate-required (value change — backtest before delegating):**
- `rsi` — bit-identical to legacy only at long windows (~200+ bars). TA-Lib seeds Wilder with an SMA of the first `period` deltas; the streaming `_calc_rsi` seeds on the first delta, so on the SHORT windows the runtime actually uses early in a session (len≥20) they diverge by **up to ~17 RSI points**. A live delegation would change early-session RSI-gated entries → backtest gate required.
- `adx` — warmup contract differs: TA-Lib needs ~2×period bars to emit a finite value, while `_calc_adx` returns a value at period+1 (partial-DX average). On short windows the engine is still `None` where legacy gives a number, so delegation changes early-session ADX availability → gate.
- `atr` — legacy is SMA-of-TR, engine is Wilder; median ~6% (stock) / ~8% (futures), tails far higher on quiet minutes. Drives Setup A/C stops + edge filters and ATR exits → needs a Setup-A/C backtest gate. (Note: `#571` evaluated the standalone-consumer ATR and chose **keep SMA**; the engine ATR would need an SMA mode, or the gate must justify the switch.)
- `bb_width` — legacy sample std (ddof=1) vs engine population std (ddof=0): a constant band-half-width shift of **2.53%** (= 1 − √(19/20)). Drives `bb_reversion` band touches → bb_reversion backtest gate.
- `stoch_k` — legacy fast %K vs engine slow %K (STOCH): median 17–25%. Either gate the fast→slow change or switch the backend to `STOCHF` to preserve the fast convention.

**RSI/MFI sentinel-contract note:** the `≥50% div` tail is flat/halted-window disagreement — legacy returns the neutral sentinel **50.0**, TA-Lib **0.0** — on illiquid constant-price names. Any RSI/MFI delegation must preserve the neutral fallback on degenerate windows or a 0.0 reads as extreme oversold.

_Generated by `scripts/analysis/shadow_parity_realdata.py`._
