# bb_reversion_15m × RegimeGate — head-to-head verdict (2026-05-22)

Spec: docs/superpowers/specs/2026-05-21-futures-approach3-regime-gate-design.md (§7 robust gate, §8 head-to-head δ, §10 triggers)
Tool: scripts/gate_futures_strategy.py --head-to-head --delta-sharpe 0.5
Data: data/kospi200f_1m_a01603.csv (T10 --single-code A01603) | holdout 2026-02-01 | min-trades 50 | 70+70 trials
Gate config: config/gates/regime_gate_default.yaml (regime_percentile_max=80, impact_score_max=70, event_window=15min, permissive_on_missing=true)
HAR-RV recompute: scripts/forecasting/recompute_har_rv_historical.py --candles-csv data/kospi200f_1m_a01603.csv --train-start 2025-08-01 --train-end 2026-01-31 --test-start 2026-02-01 --test-end 2026-03-12; wrote 3,771 rows tagged model_version='har_rv_v1_recompute'
(Yesterday-2026-05-21's BLOCKED verdict has been superseded by this run; Path A pivot via T8/T9/T10 enabled it.)

## VERDICT: FAIL (Δsharpe=0.000)

`>>> HEAD-TO-HEAD: FAIL (Δsharpe=0.000 vs δ=0.5 | gated_rescoped_pass=True)`

| Arm | OOS Sharpe | OOS MDD | OOS Return | OOS PF | OOS Trades |
|---|---|---|---|---|---|
| Baseline (no gate) | **11.7632** | 13.50% | +166.28% | 4.0952 | 40 |
| Gated (RegimeGate) | **11.7632** | 13.50% | +166.28% | 4.0952 | 40 |
| Δ | **0.000** | 0.000 | 0.00% | 0.00 | 0 |

The gated arm's OOS is **bit-for-bit identical** to baseline. Δ Sharpe = exactly 0.000.

Baseline's own robust §6 gate: `PASS (a=True b=True c=True | median_sharpe=7.14 basin=100.0% n_valid=48)` (strong: 48/70 valid train trials all non-catastrophic; median Sharpe 7.14 vs floor 0; basin 100% vs floor 25%).

Best baseline params: `bb_period=20, bb_std=2.30, bb_touch_buffer=1.09, rsi_period=19, rsi_oversold=34, rsi_overbought=79, min_bb_bandwidth=0.00717` (train Sharpe = 10.06).

Baseline OOS detail line (verbatim):
`OOS metrics: sharpe=11.7632 pf=4.0952 mdd=13.50% ret=166.2782% trades=40`

Trial counts: 140 successful, 0 failed across both studies (70 baseline + 70 gated). 2 study creations.

## Why Δ = exactly 0.000 — the actual finding

The gate at `regime_percentile_max=80` never blocked a single entry during OOS. CH query of the recompute's actual regime_percentile labels confirms why:

```
recompute regime_percentile distribution (OOS Feb 1-Mar 12, 1,887 rows):
  min=34.03  p50=34.03  p90=34.03  p99=34.03  max=34.03
  rows > 80 (would have blocked): 0 / 1,887  (0.0%)
```

**Every single label is exactly 34.03** — the value is constant across the entire OOS window.

Root cause is in `shared/forecasting/volatility_har_rv.py::forecast()`:

```python
def forecast(self, asof, current_close):
    rv_d, rv_w, rv_m = self._latest_components   # FROZEN at fit time
    pred_rv = c.beta_0 + c.beta_d * rv_d + c.beta_w * rv_w + c.beta_m * rv_m
    percentile = (self._rv_history < pred_rv).mean() * 100
    return VolForecast(..., regime_percentile=percentile, ...)
```

`self._latest_components` is set ONCE during `fit()` (line 114) and reused by every subsequent `forecast()` call regardless of `asof`. Our `recompute_and_insert` fits once on the train window then calls `forecast()` for every OOS minute — producing identical `pred_rv` and identical `regime_percentile` across all 1,887 labels. **The production live forecasting service avoids this only because it presumably refits frequently with updated daily-RV history; the one-shot historical recompute path doesn't replicate that rolling behavior.**

## So is this a gate-FAIL or a recompute-FAIL?

It is a **recompute-FAIL** — the gate's design isn't being honestly evaluated. With constant labels, no threshold setting can make the gate fire meaningfully on OOS:
- `regime_percentile_max >= 34.03` → gate never blocks (current default 80 falls here)
- `regime_percentile_max < 34.03` → gate ALWAYS blocks (would suppress every entry → trivially worse)

So the head-to-head's exact 0.000 Δ is not "the gate doesn't help" — it's "we can't tell because our regime labels are degenerate."

## Spec §10 trigger interpretation

A literal reading: head-to-head FAIL → P3-③ trigger (tick microstructure). But the FAIL is upstream-of-gate, not in the gate's design. The honest trigger is a new **P0-③' (recompute-rolling-components fix)**: modify `recompute_and_insert` to call `forecast()` with per-asof updated `(rv_d, rv_w, rv_m)` derived from the rolling RV window up to (but excluding) `asof`. Without that, NO future Approach ③ run can produce meaningful regime_percentile labels.

After that fix lands, the head-to-head re-runs verbatim — all P0+P1+T8/T9/T10 infrastructure stays as-is — and produces a real PASS/FAIL of the gate's design.

## P0+P1+Path-A artifacts (built and tested on this branch, ready when the recompute is fixed)

| Component | File | Status |
|---|---|---|
| Spec + §13 corrections | `docs/superpowers/specs/2026-05-21-...md` | merged on branch (commits `5747974`, `6e4ead3`) |
| Coverage audit CLI | `scripts/audit_forecast_coverage.py` (+ test) | 5 tests pass |
| Historical HAR-RV recompute | `scripts/forecasting/recompute_har_rv_historical.py` (+ test) | 8 tests pass; **needs rolling-components fix** to produce non-degenerate labels |
| RegimeGate filter | `shared/strategy/gates/regime_gate.py` (+ test) | 6 tests pass |
| Engine-layer gate hook | `shared/backtest/engine.py` (+ test) | 3 tests pass |
| Gate runner --gate/--head-to-head | `scripts/gate_futures_strategy.py` (+ test) | 5 tests pass (incl. tz-mismatch regression fix from this T7 run) |
| Search-space + gate-default configs | `config/optuna/futures/bb_reversion_15m.yaml`, `config/gates/regime_gate_default.yaml` | merged |
| build_clean_kospi200f_csv + --single-code (Path A++) | `scripts/forecasting/build_clean_kospi200f_csv.py` (+ test) | 7 tests pass |
| recompute --candles-csv flag | (same file as above) | merged via T9 |
| Cross-task ClickHouse-wrapper unwrap fix | (3 scripts) | merged (commit `74f1383`) |
| `_CHInputs` tz-strip-at-load fix | `scripts/gate_futures_strategy.py` (+ test) | merged (commit `4dd951c`); blocks the head-to-head crash that surfaced today |

Total: 152+ unit tests pass on this branch; ruff clean for all touched files; **all infrastructure is production-ready**. The only blocker for a real gate-design verdict is the one-line-conceptual `_latest_components` rolling-update in `recompute_and_insert`.

## Reproduce

```bash
cd <worktree>
set -a; source /home/deploy/project/kis_unified_sts/.env; set +a
# Step 1 — clean CSV (A01603 only):
python scripts/forecasting/build_clean_kospi200f_csv.py \
  --single-code A01603 --start 2025-07-01 --end 2026-03-12 \
  --out data/kospi200f_1m_a01603.csv
# Step 2 — recompute (will populate ~1,887 OOS rows; ALL with regime_percentile=34.03):
python scripts/forecasting/recompute_har_rv_historical.py \
  --candles-csv data/kospi200f_1m_a01603.csv \
  --train-start 2025-08-01 --train-end 2026-01-31 \
  --test-start 2026-02-01 --test-end 2026-03-12 --cadence-minutes 15
# Step 3 — head-to-head (~5 min; will FAIL with Δ=0 due to constant labels):
python scripts/gate_futures_strategy.py \
  --strategy bb_reversion_15m \
  --data data/kospi200f_1m_a01603.csv \
  --space config/optuna/futures/bb_reversion_15m.yaml \
  --gate config/gates/regime_gate_default.yaml \
  --head-to-head --delta-sharpe 0.5 \
  --holdout-split 2026-02-01 --min-trades 50 --trials 70
```

(TPESampler seed=42 — deterministic.)
