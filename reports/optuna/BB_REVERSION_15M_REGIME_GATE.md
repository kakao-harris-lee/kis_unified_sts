# bb_reversion_15m × RegimeGate — head-to-head verdict (2026-05-21)

Spec: docs/superpowers/specs/2026-05-21-futures-approach3-regime-gate-design.md (§7 robust gate, §8 head-to-head δ, §10 triggers)
Tool: scripts/gate_futures_strategy.py --head-to-head --delta-sharpe 0.5
Data: data/kospi200f_1m_ch_101S6000.csv | holdout 2026-02-01 | min-trades 50 | 70+70 trials (planned)
Gate config: config/gates/regime_gate_default.yaml (regime_percentile_max=80, impact_score_max=70, event_window=15min, permissive_on_missing=true)

## VERDICT: BLOCKED (data-infrastructure bottleneck, not a gate-design verdict)

The head-to-head Optuna run was NOT executed because the gate's data layer cannot supply meaningful inputs over the gate-test window. The discovery itself is the substantive finding.

## Evidence

### 1. Forecast tables are empty for the gate-test window

```
window: 2026-02-01T00:00:00 → 2026-04-24T00:00:00
vol_forecasts: total=0  live=0  recompute=0
event_scores:  total=0
coverage: 0.0% (min=90%)
```

`vol_forecasts` has 78 live rows across all time (all outside this window — the 90-day TTL evicts older rows; the live forecasting service has only been writing recently). `event_scores` has zero rows for all time — the live event-scorer has never written to this ClickHouse instance.

### 2. The HAR-RV historical recompute (Task 2) cannot fit on this data

Two attempts with different train windows both failed at the HAR-RV OOS R² threshold (the implementer set `min_r2_oos=-1.0`, already the maximally-permissive value the Pydantic field validator allows — `HARRVConfig.min_r2_oos: float = Field(default=0.10, ge=-1.0, le=1.0)` at `shared/forecasting/config.py:17`):

| Train window | Test window | Result |
|---|---|---|
| 2025-07-01 → 2026-01-31 | 2026-02-01 → 2026-04-23 | `R² OOS = -168.796` |
| 2025-08-01 → 2026-01-31 | 2026-02-01 → 2026-04-23 | `R² OOS = -127.767` |

### 3. Root cause — chronic outlier-corruption in `kospi.kospi200f_1m`

The daily-RV series derived from the source minute-bar table (`kospi.kospi200f_1m`, `code='101S6000'`) has catastrophic outliers throughout the train window:

```
AUG2025-JAN2026 daily RV (n=152 days, median=3.886e-03):
  max=6.280e-01  =  161.6× median
  days > 5×median: 23 (15.1% of days)
  days > 50×median: 6
  top outliers:
    2025-11-14: 6.28e-01  (161.6× median)
    2025-11-21: 6.28e-01  (161.5× median)
    2025-08-05: 3.81e-01  (98.0× median)
    2025-10-27: 3.51e-01  (90.3× median)
    2025-10-30: 3.38e-01  (86.9× median)
    2025-10-10: 2.23e-01  (57.3× median)
    2025-09-25: 1.91e-01  (49.1× median)
    2025-09-30: 1.68e-01  (43.3× median)
```

Interpretation: median daily-variance 3.9e-3 ≈ 10% annualized vol (plausible for KOSPI200 futures). Max daily-variance 6.3e-1 ≈ √0.63 × √252 × 100 ≈ **1258% annualized vol** — physically impossible for a sane trading day. The outliers are not isolated to one event; they are spread across Aug–Nov 2025 (15% of days). The most likely upstream cause is corrupted minute-bar OHLC values (e.g. bad high/low ticks producing absurd intra-day ranges that feed into the sum-of-squared-1m-returns realized-variance calculation).

OLS HAR-RV on this skewed input produces wildly unstable coefficients → OOS predictions far from the held-out tail mean → catastrophically negative R². The fit aborts; recompute cannot proceed.

### 4. event_scores empty regardless

Even if the vol-regime layer were fixable, `event_scores` has zero rows over all of history, so the event-impact component of the gate would be a complete no-op (PERMISSIVE pass-through for every bar). The full RegimeGate as designed cannot be exercised on this data.

## Decision

**Spec §10 P2-③ trigger does NOT fire** — head-to-head was not run (data-layer blocked); cannot claim PASS.
**Spec §10 P3-③ trigger does NOT fire** — head-to-head was not run; cannot claim FAIL of the gate's design.

A new, dedicated effort is required to investigate `kospi.kospi200f_1m` data quality for 2025-07 → 2026-01 (specifically the 23 days with daily-RV > 5× median; chiefly Aug 5, Sep 25/30, Oct 10/27/30, Nov 13/14/21). Likely angles:
- Are the corrupt rows actually present in the source KIS feed or introduced during ingestion?
- Is there a high/low validity check that should have rejected the bad ticks?
- Should the realized-variance computation winsorize 1-minute returns before squaring?
- Does the live forecasting service avoid these because of the 90-day TTL (i.e. has the issue ever affected live)?

Until that investigation completes, Approach ③ P1 cannot be decided. The P0+P1 infrastructure on this branch (audit CLI, recompute CLI, RegimeGate, engine hook, gate runner, configs) is built and tested and remains ready to use once the data layer is repaired.

## What was actually committed in P0+P1 (still valuable, reusable)

| Component | File | Status |
|---|---|---|
| Spec §13 corrections | `docs/superpowers/specs/2026-05-21-futures-approach3-regime-gate-design.md` | merged on branch |
| Coverage audit CLI | `scripts/audit_forecast_coverage.py` + test | merged, tests green |
| Historical HAR-RV recompute | `scripts/forecasting/recompute_har_rv_historical.py` + test | merged, tests green (fit fails on this dataset; the script itself is correct) |
| RegimeGate filter | `shared/strategy/gates/regime_gate.py` + test | merged, 6 tests green |
| Engine-layer gate hook | `shared/backtest/engine.py` + test | merged, 3 tests green |
| Gate runner --gate/--head-to-head | `scripts/gate_futures_strategy.py` + test | merged, 4 tests green |
| Search-space + gate-default configs | `config/optuna/futures/bb_reversion_15m.yaml`, `config/gates/regime_gate_default.yaml` | merged |
| CH-wrapper unwrap fix | (T7 follow-up commit) | merged |

Total: 152 unit tests pass on this branch; ruff clean for all touched files. All infrastructure is production-ready as far as the gate runner is concerned. The only blocker is the upstream data.

## Reproduce

```bash
cd <worktree>
set -a; source /home/deploy/project/kis_unified_sts/.env; set +a
# audit:
python scripts/audit_forecast_coverage.py --start 2026-02-01 --end 2026-04-24 \
  --expected-trading-minutes 24300 --min-coverage 0.90
# recompute (will FAIL with R² OOS catastrophic):
python scripts/forecasting/recompute_har_rv_historical.py \
  --train-start 2025-07-01 --train-end 2026-01-31 \
  --test-start 2026-02-01 --test-end 2026-04-23 --cadence-minutes 15
# data-quality diagnostic:
python - <<'PY'
from shared.db.client import get_clickhouse_client
from shared.db.config import ClickHouseConfig
from shared.forecasting.realized_variance import daily_rv_series
import pandas as pd
cli = get_clickhouse_client(ClickHouseConfig.from_env()).get_sync_client()
rows = cli.execute(
    "SELECT datetime, open, high, low, close, volume FROM kospi.kospi200f_1m "
    "WHERE code='101S6000' AND datetime >= '2025-08-01' AND datetime < '2026-02-01' "
    "ORDER BY datetime")
df = pd.DataFrame(rows, columns=["datetime","open","high","low","close","volume"])
df["datetime"] = pd.to_datetime(df["datetime"], utc=True); df = df.set_index("datetime")
rv = daily_rv_series(df)
print(rv.nlargest(10))
PY
```
