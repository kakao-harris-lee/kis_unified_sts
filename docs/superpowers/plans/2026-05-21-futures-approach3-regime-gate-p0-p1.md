# Approach ③ — Regime/Event Gate (P0+P1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a regime/event gate over `bb_reversion_15m` using already-persisted `vol_forecasts` + `event_scores` + `macro_history`; run a decisive head-to-head against the bare baseline through the same robust §6 gate; record terminal PASS (→P2-③) or FAIL (→P3-③) verdict.

**Architecture:** Strategy-agnostic engine-layer hook (between `signal = strategy.on_bar(bar)` and the BUY/SELL dispatch at `shared/backtest/engine.py:326-360`) that consults a pure `RegimeGate` filter. The gate reads vol_forecasts (HAR-RV percentile), event_scores (per-event impact), and macro_history (overnight US direction). PERMISSIVE on missing inputs — never silently drops trades. Backtest-only in this plan; live wiring is P2-③ (trigger-gated).

**Tech Stack:** Python 3.11, `clickhouse_driver` (sync, native 9000), Optuna TPE, the just-shipped `shared/backtest/robust_gate.py` and `scripts/gate_futures_strategy.py`, the existing `shared/forecasting/volatility_har_rv.py` HAR-RV math (annualized %, 0–100 empirical CDF percentile), `shared/backtest/macro_history.py` (yfinance, `sp500_change_pct` percentage).

**Spec:** `docs/superpowers/specs/2026-05-21-futures-approach3-regime-gate-design.md` (read §7 gate, §8 head-to-head δ, §9 PERMISSIVE-degrade, §10 trigger table, §13 — added by Task 0).

**Branch/worktree:** all work on `docs/futures-approach3-regime-gate-design` in worktree `/home/deploy/wt-futures-approach3-regime-gate` (off `origin/main` 739728c, which already includes yesterday's P0+P1). NEVER `main`/`runtime/main-current`. The worktree has no local `.venv`; use the shared interpreter at `/home/deploy/project/kis_unified_sts/.venv/bin/{python,pytest}`. Stage explicit paths only; every commit ends with `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `docs/superpowers/specs/2026-05-21-...md` (modify) | Append §13 plan-time corrections (6 items the extraction surfaced) | 0 |
| `scripts/audit_forecast_coverage.py` (create) | CLI: coverage % + gap list for vol_forecasts / event_scores over a window | 1 |
| `tests/unit/forecasting/test_audit_coverage.py` (create) | Coverage math + gap detection (mocked CH client) | 1 |
| `scripts/forecasting/recompute_har_rv_historical.py` (create) | Fit HAR-RV on train window of daily RV, write `vol_forecasts` rows for OOS window with `model_version="har_rv_v1_recompute"` | 2 |
| `tests/unit/forecasting/test_historical_recompute.py` (create) | Recompute math + tagging + look-ahead boundary | 2 |
| `shared/strategy/gates/__init__.py` (create) | Package marker | 3 |
| `shared/strategy/gates/regime_gate.py` (create) | `RegimeGate.allow(ts, asset, ctx) → (bool, reason)`; vol/event/macro inputs; PERMISSIVE degrade | 3 |
| `tests/unit/strategy/gates/test_regime_gate.py` (create) | Block / allow / PERMISSIVE / look-ahead-guard unit tests | 3 |
| `shared/backtest/engine.py` (modify, lines 326–360) | Optional `gate=None` ctor arg; on each entry signal, query gate; force `SignalType.HOLD` on block (backward-compatible no-op when gate=None) | 4 |
| `tests/unit/backtest/test_engine_gate.py` (create) | Gate=None unchanged; gate-block forces HOLD; gate-allow unchanged | 4 |
| `scripts/gate_futures_strategy.py` (modify) | Add `--gate <yaml>` + `--head-to-head` flags; thread RegimeGate through to BacktestEngine | 5 |
| `tests/unit/backtest/test_gate_cli_regime_flag.py` (create) | --gate parses; engine receives gate; --head-to-head runs both passes | 5 |
| `config/optuna/futures/bb_reversion_15m.yaml` (create) | Search space (mirrors probe_bb_reversion_15m_gate.py:110–133) | 6 |
| `config/gates/regime_gate_default.yaml` (create) | Default RegimeGate config (percentile/event/direction thresholds + PERMISSIVE flag) | 6 |
| `reports/optuna/BB_REVERSION_15M_REGIME_GATE.md` (create) | Recorded head-to-head verdict (baseline vs gated; Δ Sharpe vs δ; PASS→P2-③ / FAIL→P3-③) | 7 |

---

### Task 0: Append §13 plan-time spec corrections (the extraction's 6 findings)

**Files:** Modify `docs/superpowers/specs/2026-05-21-futures-approach3-regime-gate-design.md` (append a new section at the end, before the closing brainstorm note).

This mirrors yesterday's §12 corrections pattern — fold runtime-discovered facts into the spec so the audit trail is honest, before the plan starts depending on them.

- [ ] **Step 1: Append the §13 corrections section**

Insert immediately before the final `*Brainstorm note: ...*` line:

```markdown
## 13. Plan-time corrections (2026-05-21, from code extraction)

Discovered while extracting exact code shapes for the plan; folded in so the plan is factually grounded. Cf. yesterday's §12.

1. **The "block" path is `SignalType.HOLD`, NOT `signal_direction = NEUTRAL`.** `shared/backtest/engine.py:36-41` defines `SignalType{HOLD, BUY, SELL}`; there is no NEUTRAL. `signal_direction` (`"long"`/`"short"`) lives in `signal.metadata`, not as a top-level field on `Signal`. The §7 wording is amended: *block → force `signal = SignalType.HOLD` before the BUY/SELL dispatch.*
2. **The gate-injection point is the ENGINE, not the adapter.** `shared/backtest/engine.py:326` calls `signal = self.strategy.on_bar(bar)`; the BUY/SELL dispatch follows at 331–360. Injecting the gate here keeps it strategy-agnostic (applies to ANY strategy without touching adapter or strategy code), simpler, and DRY. C4 in §6 is amended accordingly.
3. **`forecast_pct` is annualized percent** (e.g. `30` means 30%), not a fraction or unit-pct. `shared/forecasting/volatility_har_rv.py:140`: `forecast_pct = sqrt(pred_rv * 252) * 100`. **`regime_percentile` is the empirical CDF position scaled 0–100** (line 149: `(self._rv_history < pred_rv).mean() * 100`). Gate thresholds in `regime_gate_default.yaml` use these natural units (e.g. `regime_percentile_max: 80.0` = block when predicted RV exceeds the 80th percentile of in-fit daily RV history).
4. **`MacroSnapshot.sp500_change_pct` is a percentage, no precomputed direction.** Direction must be derived via `math.copysign(1.0, sp500_change_pct)` (same pattern Setup A uses at `shared/decision/setups/gap_reversion.py:133`).
5. **`vol_forecasts` TTL is 90 DAY** (`infra/clickhouse/migrations/V6__forecast_tables.sql`). For any backtest window older than ~90 days, live-emitted vol_forecasts have been TTL-evicted → C2 (historical HAR-RV recompute) is **required**, not optional, for the bb_reversion_15m gate-test data range (2025-07-01 → 2026-04-23). The recompute writes rows with `model_version = "har_rv_v1_recompute"`, distinct from live `"har_rv_v1"` (§9 isolation rule preserved).
6. **DDL location** for `vol_forecasts` / `event_scores` is `infra/clickhouse/migrations/V6__forecast_tables.sql`, **not** `shared/db/client.py::SCHEMAS`. The plan's table-existence assumptions reference the migration file.

Outside the spec: **the daily RV input the HAR-RV `fit()` expects is a `pd.Series` keyed by date** (`shared/forecasting/volatility_har_rv.py:59`), constructible from `kospi.kospi200f_1m` minute candles via `shared.forecasting.realized_variance.daily_rv_series(...)` (cf. `scripts/forecasting/refit_har_rv.py:52-65`). The plan's recompute task wires this end-to-end.
```

- [ ] **Step 2: Commit**

```bash
cd /home/deploy/wt-futures-approach3-regime-gate
git add docs/superpowers/specs/2026-05-21-futures-approach3-regime-gate-design.md
git commit -m "$(cat <<'EOF'
docs(futures): spec §13 plan-time corrections (Approach ③)

Six findings from code extraction folded into the spec:
SignalType.HOLD (not NEUTRAL); engine-layer gate hook (not adapter);
forecast_pct annualized %; regime_percentile 0–100; vol_forecasts
90d TTL → recompute is required; DDL lives in V6 migration file.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 1: Coverage audit CLI

**Files:** Create `scripts/audit_forecast_coverage.py`, `tests/unit/forecasting/__init__.py` (empty if missing), `tests/unit/forecasting/test_audit_coverage.py`.

Audits the actual on-disk presence of `vol_forecasts` (per-minute, expected ~1 row/min on trading minutes) and `event_scores` (sparse) for a window, reports coverage % + the first/last gap of each, distinguishing `model_version="har_rv_v1"` (live) vs `"har_rv_v1_recompute"` (post-hoc, Task 2 output).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/forecasting/test_audit_coverage.py
import datetime as dt
import importlib.util
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "afc", _REPO / "scripts" / "audit_forecast_coverage.py")
afc = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(afc)


class _FakeClient:
    def __init__(self, vol_rows, event_rows):
        self.vol_rows = vol_rows
        self.event_rows = event_rows
    def execute(self, sql, params=None):
        if "vol_forecasts" in sql:
            return self.vol_rows
        if "event_scores" in sql:
            return self.event_rows
        return []


def test_coverage_full(monkeypatch):
    # 60 minutes × 1 trading minute each → 100% live coverage
    rows = [(60, 60, 0)]  # (total, live_count, recompute_count)
    monkeypatch.setattr(afc, "_get_client", lambda: _FakeClient(rows, [(0,)]))
    r = afc.audit_window(
        start=dt.datetime(2026, 4, 1, 0, 0), end=dt.datetime(2026, 4, 1, 1, 0))
    assert r["vol_total"] == 60
    assert r["vol_live"] == 60
    assert r["vol_recompute"] == 0
    assert r["event_total"] == 0


def test_coverage_recompute_only(monkeypatch):
    rows = [(60, 0, 60)]
    monkeypatch.setattr(afc, "_get_client", lambda: _FakeClient(rows, [(5,)]))
    r = afc.audit_window(
        start=dt.datetime(2025, 9, 1, 0, 0), end=dt.datetime(2025, 9, 1, 1, 0))
    assert r["vol_live"] == 0
    assert r["vol_recompute"] == 60
    assert r["event_total"] == 5


def test_main_prints_verdict(capsys, monkeypatch):
    monkeypatch.setattr(
        afc, "_get_client",
        lambda: _FakeClient([(60, 30, 30)], [(2,)]))
    rc = afc.main(["--start", "2026-04-01", "--end", "2026-04-02"])
    out = capsys.readouterr().out
    assert "vol_forecasts" in out
    assert "event_scores" in out
    assert rc in (0, 1)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/deploy/wt-futures-approach3-regime-gate
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/forecasting/test_audit_coverage.py -v
```
Expected: FAIL — `scripts/audit_forecast_coverage.py` does not exist.

- [ ] **Step 3: Create the CLI**

```python
#!/usr/bin/env python3
"""Coverage audit for vol_forecasts + event_scores (spec 2026-05-21 P0-③ T1).

Reports actual on-disk presence over a window. Distinguishes
model_version='har_rv_v1' (live) from 'har_rv_v1_recompute' (post-hoc)
so the operator knows whether Task 2 (historical recompute) is needed.
Exit code: 0 if vol coverage >= --min-coverage, else 1.
"""
from __future__ import annotations
import argparse, sys
import datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.db.client import get_clickhouse_client
from shared.db.config import ClickHouseConfig


def _get_client():
    return get_clickhouse_client(ClickHouseConfig.from_env())


def _ch_naive(d):
    return d.replace(tzinfo=None) if getattr(d, "tzinfo", None) else d


def audit_window(start: dt.datetime, end: dt.datetime) -> dict:
    cli = _get_client()
    vol = cli.execute(
        "SELECT count() AS total, "
        "countIf(model_version = 'har_rv_v1') AS live, "
        "countIf(model_version = 'har_rv_v1_recompute') AS recompute "
        "FROM kospi.vol_forecasts "
        "WHERE asof >= %(s)s AND asof < %(e)s",
        {"s": _ch_naive(start), "e": _ch_naive(end)},
    )
    ev = cli.execute(
        "SELECT count() FROM kospi.event_scores "
        "WHERE asof >= %(s)s AND asof < %(e)s",
        {"s": _ch_naive(start), "e": _ch_naive(end)},
    )
    total, live, recompute = vol[0] if vol else (0, 0, 0)
    event_total = ev[0][0] if ev else 0
    return {
        "vol_total": int(total),
        "vol_live": int(live),
        "vol_recompute": int(recompute),
        "event_total": int(event_total),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD or ISO datetime")
    ap.add_argument("--end", required=True)
    ap.add_argument(
        "--expected-trading-minutes", type=int, default=0,
        help="expected count; if >0, coverage % is reported")
    ap.add_argument(
        "--min-coverage", type=float, default=0.90,
        help="exit 1 if vol coverage < this fraction (default 0.90)")
    a = ap.parse_args(argv)
    s = dt.datetime.fromisoformat(a.start)
    e = dt.datetime.fromisoformat(a.end)
    r = audit_window(s, e)
    print(f"window: {s.isoformat()}  →  {e.isoformat()}")
    print(
        f"vol_forecasts: total={r['vol_total']}  "
        f"live={r['vol_live']}  recompute={r['vol_recompute']}")
    print(f"event_scores:  total={r['event_total']}")
    if a.expected_trading_minutes > 0:
        cov = r["vol_total"] / a.expected_trading_minutes
        print(f"coverage: {cov:.1%}  (min={a.min_coverage:.0%})")
        if cov < a.min_coverage:
            print("VERDICT: insufficient — run Task 2 historical recompute")
            return 1
    print("VERDICT: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify pass**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/forecasting/test_audit_coverage.py -v
```
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/audit_forecast_coverage.py tests/unit/forecasting/__init__.py tests/unit/forecasting/test_audit_coverage.py
git commit -m "$(cat <<'EOF'
feat(forecasting): coverage audit CLI (spec 2026-05-21 P0-③ T1)

Audits vol_forecasts + event_scores presence over a window;
distinguishes live (har_rv_v1) from recompute (har_rv_v1_recompute);
exits 1 when coverage below --min-coverage so Task 2 can be triggered.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Historical HAR-RV recompute

**Files:** Create `scripts/forecasting/recompute_har_rv_historical.py`, `tests/unit/forecasting/test_historical_recompute.py`.

The bb_reversion_15m gate test runs over data spanning 2025-07-01 → 2026-04-23. Live vol_forecasts older than 90 days have been TTL-evicted; we need to repopulate them post-hoc. **Key look-ahead discipline:** fit `VolatilityForecaster` ONCE on a training window of daily RV (e.g. 2025-07-01 → train_cutoff), then apply the frozen coefficients to compute forecasts for every minute of the OOS window. Rows tagged `model_version = "har_rv_v1_recompute"` (§13 correction 5) so a backtest can never mistake them for live-emitted values. For the in-sample portion of the gate's Optuna run (data before `--train-cutoff`), the gate will rely on PERMISSIVE pass-through (§9) — no synthetic forecasts there, deliberately.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/forecasting/test_historical_recompute.py
import datetime as dt
import importlib.util
import pathlib

import pandas as pd
import pytest

_REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "hrr", _REPO / "scripts" / "forecasting" / "recompute_har_rv_historical.py")
hrr = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(hrr)


def test_tag_is_recompute():
    assert hrr.RECOMPUTE_MODEL_VERSION == "har_rv_v1_recompute"
    # Must NOT collide with live tag
    from shared.forecasting.volatility_har_rv import VolatilityForecaster
    assert hrr.RECOMPUTE_MODEL_VERSION != VolatilityForecaster.MODEL_VERSION


def test_lookahead_guard_rejects_test_overlapping_train():
    # If train ends 2026-02-01 and test starts 2026-01-15, that's leakage.
    with pytest.raises(ValueError, match="overlap"):
        hrr._validate_split(
            train_end=dt.date(2026, 2, 1), test_start=dt.date(2026, 1, 15))


def test_fit_then_apply_produces_rows_at_15min_cadence(monkeypatch):
    # Tiny synthetic RV series + dummy fit, then apply over 1h test window
    rng = pd.date_range("2025-09-01", periods=90, freq="D")
    rv = pd.Series(0.0001 + 1e-6 * (rng.dayofyear % 7), index=rng.date)
    rows_written = []

    def fake_insert(client, rows):
        rows_written.extend(rows)

    monkeypatch.setattr(hrr, "_insert_rows", fake_insert)

    hrr.recompute_and_insert(
        train_rv=rv,
        test_minutes=pd.date_range(
            "2025-12-01 09:00", "2025-12-01 10:00", freq="15min"),
        current_close=380.0,
        client=None,
    )
    assert len(rows_written) == 5
    # Every row tagged recompute
    assert all(r[5] == "har_rv_v1_recompute" for r in rows_written)
    # forecast_pct in plausible annualized-percent range (10–100)
    assert all(10.0 < r[2] < 100.0 for r in rows_written)
    # regime_percentile in [0, 100]
    assert all(0.0 <= r[4] <= 100.0 for r in rows_written)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/forecasting/test_historical_recompute.py -v
```
Expected: FAIL — `scripts/forecasting/recompute_har_rv_historical.py` does not exist.

- [ ] **Step 3: Create the recompute tool**

```python
#!/usr/bin/env python3
"""Historical HAR-RV recompute for backtest replay (spec 2026-05-21 P0-③ T2).

Fits VolatilityForecaster ONCE on a training window of daily RV (from
kospi.kospi200f_1m), then applies the frozen coefficients to every
15-minute timestamp in the OOS window. Writes vol_forecasts rows
tagged model_version='har_rv_v1_recompute' so they are never confused
with live publishes (har_rv_v1). Look-ahead-safe: train_end < test_start
is enforced.
"""
from __future__ import annotations
import argparse, sys
import datetime as dt
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.db.client import get_clickhouse_client
from shared.db.config import ClickHouseConfig
from shared.forecasting.realized_variance import daily_rv_series
from shared.forecasting.volatility_har_rv import VolatilityForecaster

RECOMPUTE_MODEL_VERSION = "har_rv_v1_recompute"
_PROXY_CODE = "101S6000"  # connected futures, same as live forecaster


def _validate_split(train_end: dt.date, test_start: dt.date) -> None:
    if test_start <= train_end:
        raise ValueError(
            f"train/test overlap: train_end={train_end} >= test_start={test_start}")


def _fetch_minute_candles(client, start: dt.date, end: dt.date) -> pd.DataFrame:
    rows = client.execute(
        "SELECT datetime, open, high, low, close, volume "
        "FROM kospi.kospi200f_1m "
        "WHERE code = %(c)s AND datetime >= %(s)s AND datetime < %(e)s "
        "ORDER BY datetime",
        {"c": _PROXY_CODE, "s": start, "e": end},
    )
    return pd.DataFrame(
        rows, columns=["datetime", "open", "high", "low", "close", "volume"])


def _insert_rows(client, rows: list[tuple]) -> int:
    if client is None or not rows:
        return 0
    client.execute(
        "INSERT INTO kospi.vol_forecasts "
        "(asof, horizon_minutes, forecast_pct, forecast_atr_equivalent, "
        "regime_percentile, model_version) VALUES",
        rows,
    )
    return len(rows)


def recompute_and_insert(
    train_rv: pd.Series,
    test_minutes: pd.DatetimeIndex,
    current_close: float,
    client,
) -> int:
    """Fit on train_rv, forecast at every test_minutes timestamp, insert."""
    forecaster = VolatilityForecaster()
    forecaster.fit(train_rv)
    rows: list[tuple] = []
    for ts in test_minutes:
        asof = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
        if getattr(asof, "tzinfo", None) is not None:
            asof = asof.replace(tzinfo=None)
        vf = forecaster.forecast(asof, current_close=current_close)
        rows.append((
            asof, vf.horizon_minutes, vf.forecast_pct,
            vf.forecast_atr_equivalent, vf.regime_percentile,
            RECOMPUTE_MODEL_VERSION,
        ))
    return _insert_rows(client, rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train-start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--train-end", required=True, help="exclusive")
    ap.add_argument("--test-start", required=True)
    ap.add_argument("--test-end", required=True)
    ap.add_argument("--cadence-minutes", type=int, default=15)
    a = ap.parse_args(argv)

    ts = dt.date.fromisoformat(a.train_start)
    te = dt.date.fromisoformat(a.train_end)
    xs = dt.date.fromisoformat(a.test_start)
    xe = dt.date.fromisoformat(a.test_end)
    _validate_split(te, xs)

    client = get_clickhouse_client(ClickHouseConfig.from_env())
    train_df = _fetch_minute_candles(client, ts, te)
    if train_df.empty:
        print(f"ERROR: no minute candles in train window {ts}..{te}")
        return 2
    train_rv = daily_rv_series(train_df)

    test_minutes = pd.date_range(
        start=f"{xs.isoformat()} 09:00",
        end=f"{xe.isoformat()} 15:30",
        freq=f"{a.cadence_minutes}min",
    )
    test_df = _fetch_minute_candles(client, xs, xe)
    last_close = float(test_df["close"].iloc[-1]) if not test_df.empty else 380.0

    n = recompute_and_insert(train_rv, test_minutes, last_close, client)
    print(f"wrote {n} vol_forecasts rows (model_version={RECOMPUTE_MODEL_VERSION})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify pass**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/forecasting/test_historical_recompute.py -v
```
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add scripts/forecasting/recompute_har_rv_historical.py tests/unit/forecasting/test_historical_recompute.py
git commit -m "$(cat <<'EOF'
feat(forecasting): historical HAR-RV recompute (spec 2026-05-21 P0-③ T2)

Fits VolatilityForecaster on a train window of daily RV, applies
the frozen coefficients to OOS minutes, writes vol_forecasts rows
tagged 'har_rv_v1_recompute' (distinct from live 'har_rv_v1') so
backtest replay can never confuse them. Look-ahead-safe.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `RegimeGate` filter (pure module)

**Files:** Create `shared/strategy/gates/__init__.py` (empty), `shared/strategy/gates/regime_gate.py`, `tests/unit/strategy/gates/__init__.py` (empty), `tests/unit/strategy/gates/test_regime_gate.py`.

`RegimeGate.allow(ts, asset, ctx) → (bool, reason)`. Inputs: latest `vol_forecasts` row at `asof <= ts`, any `event_scores` rows within ± `event_window_minutes`, the day's `MacroSnapshot` (overnight US S&P direction). Config-driven thresholds (Task 6 supplies the YAML). Missing inputs → **PERMISSIVE pass-through** (§9). Look-ahead guard: any row with `asof > ts` is rejected.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/strategy/gates/test_regime_gate.py
import datetime as dt
import math

from shared.strategy.gates.regime_gate import RegimeGate, GateConfig


def _cfg(**kw):
    base = dict(
        regime_percentile_max=80.0,
        impact_score_max=70,
        event_window_minutes=15,
        require_overnight_us_direction=False,
        permissive_on_missing=True,
    )
    base.update(kw)
    return GateConfig(**base)


class _StubInputs:
    def __init__(self, vol=None, events=(), macro_sp500_pct=None):
        self.vol = vol
        self.events = list(events)
        self.macro_sp500_pct = macro_sp500_pct
    def latest_vol_at(self, ts):
        return self.vol  # tuple(asof, regime_percentile) or None
    def events_within(self, ts, window_min):
        return self.events  # list of (asof, impact_score)
    def macro_for(self, date):
        return self.macro_sp500_pct  # float or None


def test_allow_when_regime_low_no_events():
    g = RegimeGate(_cfg(), _StubInputs(
        vol=(dt.datetime(2026, 3, 1, 9, 0), 50.0), events=()))
    allow, reason = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures",
        signal_direction="long")
    assert allow is True
    assert reason == "regime_ok"


def test_block_when_regime_high():
    g = RegimeGate(_cfg(), _StubInputs(
        vol=(dt.datetime(2026, 3, 1, 9, 0), 92.5), events=()))
    allow, reason = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures", signal_direction="long")
    assert allow is False
    assert "regime_percentile" in reason


def test_block_when_recent_high_impact_event():
    g = RegimeGate(_cfg(), _StubInputs(
        vol=(dt.datetime(2026, 3, 1, 9, 0), 50.0),
        events=[(dt.datetime(2026, 3, 1, 9, 5), 85)]))
    allow, reason = g.allow(
        dt.datetime(2026, 3, 1, 9, 10), "futures", signal_direction="long")
    assert allow is False
    assert "impact_score" in reason


def test_overnight_us_direction_alignment_blocks_opposite():
    g = RegimeGate(_cfg(require_overnight_us_direction=True),
        _StubInputs(vol=(dt.datetime(2026, 3, 1, 9, 0), 50.0),
                    macro_sp500_pct=-1.2))  # US down
    allow, reason = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures", signal_direction="long")
    assert allow is False
    assert "overnight" in reason


def test_permissive_on_missing_vol_allows():
    g = RegimeGate(_cfg(), _StubInputs(vol=None, events=()))
    allow, reason = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures", signal_direction="long")
    assert allow is True
    assert reason == "permissive_missing_vol"


def test_lookahead_guard_rejects_future_vol():
    # vol asof is AFTER the decision ts — must NOT be used
    g = RegimeGate(_cfg(), _StubInputs(
        vol=(dt.datetime(2026, 3, 1, 9, 5), 92.5), events=()))
    allow, reason = g.allow(
        dt.datetime(2026, 3, 1, 9, 0), "futures", signal_direction="long")
    # Future row treated as MISSING (permissive)
    assert allow is True
    assert reason == "permissive_missing_vol"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/gates/test_regime_gate.py -v
```
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create the module**

```python
# shared/strategy/gates/regime_gate.py
"""Regime/event gate for futures entries (spec 2026-05-21 P1-③ T3).

Pure filter: given a decision timestamp + signal direction, returns
(allow: bool, reason: str). Reads vol_forecasts (HAR-RV regime),
event_scores (per-event impact), MacroSnapshot (overnight US sp500_change_pct).
Missing inputs → PERMISSIVE pass-through (§9). Look-ahead-safe: vol rows
with asof > ts are treated as MISSING, never used.
"""
from __future__ import annotations
import math
from dataclasses import dataclass
import datetime as dt


@dataclass
class GateConfig:
    regime_percentile_max: float = 80.0      # 0–100; block when > this
    impact_score_max: int = 70               # 0–100; block when any event in window > this
    event_window_minutes: int = 15
    require_overnight_us_direction: bool = False  # if True, long needs sp500_pct > 0
    permissive_on_missing: bool = True


class RegimeGate:
    """Strategy-agnostic gate. `inputs` is a duck-typed source with three
    methods: latest_vol_at(ts) → (asof, regime_percentile) | None;
    events_within(ts, window_min) → list[(asof, impact_score)];
    macro_for(date) → sp500_change_pct (percent) | None.
    """

    def __init__(self, config: GateConfig, inputs):
        self._cfg = config
        self._inputs = inputs

    def allow(
        self, ts: dt.datetime, asset: str, signal_direction: str = "long",
    ) -> tuple[bool, str]:
        cfg = self._cfg

        # 1) regime check (look-ahead-safe: future rows treated as missing)
        vol = self._inputs.latest_vol_at(ts)
        if vol is not None and vol[0] is not None and vol[0] > ts:
            vol = None  # future row → missing
        if vol is None:
            if not cfg.permissive_on_missing:
                return (False, "missing_vol_non_permissive")
            # fall through (do not return yet — still check events/overnight)
            regime_reason = "permissive_missing_vol"
        else:
            _, regime_pct = vol
            if regime_pct > cfg.regime_percentile_max:
                return (False, f"regime_percentile={regime_pct:.1f}>max")
            regime_reason = "regime_ok"

        # 2) event check
        events = self._inputs.events_within(ts, cfg.event_window_minutes)
        for asof, impact in events:
            if asof is not None and asof > ts:
                continue  # future event → look-ahead skip
            if impact > cfg.impact_score_max:
                return (False, f"impact_score={impact}>max")

        # 3) overnight US direction alignment (optional)
        if cfg.require_overnight_us_direction:
            sp500_pct = self._inputs.macro_for(ts.date())
            if sp500_pct is None:
                if not cfg.permissive_on_missing:
                    return (False, "missing_macro_non_permissive")
                # fall through allow
            else:
                us_dir = math.copysign(1.0, sp500_pct)
                want = 1.0 if signal_direction == "long" else -1.0
                if us_dir != want:
                    return (False, f"overnight_us_dir={us_dir} vs {signal_direction}")

        return (True, regime_reason)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/gates/test_regime_gate.py -v
```
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/strategy/gates/__init__.py shared/strategy/gates/regime_gate.py tests/unit/strategy/gates/__init__.py tests/unit/strategy/gates/test_regime_gate.py
git commit -m "$(cat <<'EOF'
feat(gates): RegimeGate filter (spec 2026-05-21 P1-③ T3)

Pure (vol_forecasts, event_scores, macro_overnight) filter with
PERMISSIVE-on-missing degrade and look-ahead-safe future-row rejection.
Returns (allow, reason); strategy-agnostic; no engine coupling yet.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Engine-layer gate hook (`shared/backtest/engine.py`)

**Files:** Modify `shared/backtest/engine.py` (constructor adds `gate=None`; the entry-dispatch region ~lines 326–360 forces `SignalType.HOLD` on gate block). Create `tests/unit/backtest/test_engine_gate.py`.

This is the §13-correction-2 architecture: strategy-agnostic, the gate sits at the engine layer. Backward-compatible: existing callers passing no `gate=` kw get a no-op (None → never blocks).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/backtest/test_engine_gate.py
import datetime as dt
from unittest.mock import MagicMock

from shared.backtest.engine import BacktestEngine, SignalType


def _bar(ts):
    return {"datetime": ts, "open": 100, "high": 101, "low": 99,
            "close": 100, "volume": 1000, "code": "X", "name": "X"}


def test_no_gate_passthrough_buy_opens_position():
    strat = MagicMock()
    strat.on_bar.return_value = SignalType.BUY
    strat.required_indicators = ()
    cfg = MagicMock()
    cfg.cost = MagicMock(commission_rate=0.0, slippage_rate=0.0, tax_rate=0.0)
    cfg.initial_capital = 10_000_000
    cfg.position_size_pct = 100.0
    cfg.max_positions = 1
    cfg.point_value = 50_000
    cfg.lookahead_guard_mode = "off"
    eng = BacktestEngine(strat, cfg)  # no gate → backward-compatible
    eng._open_position = MagicMock()
    eng.on_bar(_bar(dt.datetime(2026, 3, 1, 9, 0)))
    eng._open_position.assert_called_once()


def test_gate_block_forces_hold_no_open():
    strat = MagicMock()
    strat.on_bar.return_value = SignalType.BUY
    strat.required_indicators = ()
    cfg = MagicMock()
    cfg.cost = MagicMock(commission_rate=0.0, slippage_rate=0.0, tax_rate=0.0)
    cfg.initial_capital = 10_000_000
    cfg.position_size_pct = 100.0
    cfg.max_positions = 1
    cfg.point_value = 50_000
    cfg.lookahead_guard_mode = "off"
    gate = MagicMock()
    gate.allow.return_value = (False, "regime_high")
    eng = BacktestEngine(strat, cfg, gate=gate)
    eng._open_position = MagicMock()
    eng.on_bar(_bar(dt.datetime(2026, 3, 1, 9, 0)))
    eng._open_position.assert_not_called()
    gate.allow.assert_called_once()


def test_gate_allow_buy_still_opens():
    strat = MagicMock()
    strat.on_bar.return_value = SignalType.BUY
    strat.required_indicators = ()
    cfg = MagicMock()
    cfg.cost = MagicMock(commission_rate=0.0, slippage_rate=0.0, tax_rate=0.0)
    cfg.initial_capital = 10_000_000
    cfg.position_size_pct = 100.0
    cfg.max_positions = 1
    cfg.point_value = 50_000
    cfg.lookahead_guard_mode = "off"
    gate = MagicMock()
    gate.allow.return_value = (True, "regime_ok")
    eng = BacktestEngine(strat, cfg, gate=gate)
    eng._open_position = MagicMock()
    eng.on_bar(_bar(dt.datetime(2026, 3, 1, 9, 0)))
    eng._open_position.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/backtest/test_engine_gate.py -v
```
Expected: FAIL — `BacktestEngine.__init__` does not accept `gate=` yet.

- [ ] **Step 3: Add the gate hook to the engine**

In `shared/backtest/engine.py`, the constructor (search for `def __init__(self, strategy`) gains an optional `gate=None` keyword param stored on `self._gate`. In the entry-dispatch region (currently line 326 onward: `signal = self.strategy.on_bar(bar)` followed by BUY/SELL branches at ~331 and ~342), insert one filter between the signal read and the BUY/SELL dispatch:

```python
# 전략 시그널 생성
signal = self.strategy.on_bar(bar)

# Gate (spec 2026-05-21 P1-③ T4): strategy-agnostic regime/event filter.
# Backward-compatible: when self._gate is None this is a pure no-op.
if self._gate is not None and signal in (SignalType.BUY, SignalType.SELL):
    direction = "long" if signal == SignalType.BUY else "short"
    allow, _reason = self._gate.allow(
        ts=timestamp, asset=code, signal_direction=direction)
    if not allow:
        signal = SignalType.HOLD
```

(Exact variable names `timestamp`/`code` are already in scope in this region — confirm by reading the current `on_bar` body before editing.) Do NOT modify any other behavior; the BUY/SELL dispatch + `_open_position` calls stay byte-identical.

- [ ] **Step 4: Run tests to verify pass**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/backtest/test_engine_gate.py -v
```
Expected: PASS (3 passed).

- [ ] **Step 5: Regression — existing backtest suite green**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/backtest/ -q
```
Expected: 0 failures (backward-compat preserved by `gate=None` default).

- [ ] **Step 6: Commit**

```bash
git add shared/backtest/engine.py tests/unit/backtest/test_engine_gate.py
git commit -m "$(cat <<'EOF'
feat(backtest): engine-layer regime gate hook (spec 2026-05-21 P1-③ T4)

Optional gate= ctor arg; on entry signal, queries gate; on block,
forces SignalType.HOLD before _open_position. Strategy-agnostic.
gate=None → backward-compatible no-op (regression suite green).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: `gate_futures_strategy.py` — `--gate` + `--head-to-head`

**Files:** Modify `scripts/gate_futures_strategy.py`. Create `tests/unit/backtest/test_gate_cli_regime_flag.py`.

Wire the runner so a gate YAML config + a head-to-head mode work end-to-end. Head-to-head runs the SAME Optuna search twice (baseline no-gate, then gated), prints both verdicts, and reports `Δ Sharpe = gated_OOS_Sharpe - baseline_OOS_Sharpe`. Spec §8 head-to-head δ is enforced at the verdict-print level: `PASS only if rg_gated["pass"] AND Δ Sharpe >= --delta-sharpe AND gated MDD <= baseline MDD`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/backtest/test_gate_cli_regime_flag.py
import importlib.util, pathlib

_REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "gfs", _REPO / "scripts" / "gate_futures_strategy.py")
gfs = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(gfs)


def test_gate_yaml_loader_minimal(tmp_path):
    y = tmp_path / "g.yaml"
    y.write_text(
        "regime_percentile_max: 75.0\n"
        "impact_score_max: 60\n"
        "event_window_minutes: 10\n"
        "require_overnight_us_direction: false\n"
        "permissive_on_missing: true\n")
    cfg = gfs.load_gate_config(str(y))
    assert cfg.regime_percentile_max == 75.0
    assert cfg.impact_score_max == 60
    assert cfg.event_window_minutes == 10
    assert cfg.require_overnight_us_direction is False
    assert cfg.permissive_on_missing is True


def test_head_to_head_delta_computation():
    # Δ = gated OOS Sharpe − baseline OOS Sharpe; pass iff Δ ≥ delta AND
    # gated MDD ≤ baseline MDD AND rescoped_gate(study_gated, oos_gated).pass
    baseline = {"sharpe_ratio": 5.0, "max_drawdown_pct": 4.5}
    gated = {"sharpe_ratio": 5.8, "max_drawdown_pct": 4.0}
    ok, delta = gfs.head_to_head_verdict(
        baseline_oos=baseline, gated_oos=gated, delta_min=0.5,
        gated_gate_pass=True)
    assert ok is True
    assert round(delta, 4) == 0.8

    # Δ below threshold → FAIL
    ok2, _ = gfs.head_to_head_verdict(
        baseline_oos=baseline, gated_oos={"sharpe_ratio": 5.2,
                                           "max_drawdown_pct": 4.0},
        delta_min=0.5, gated_gate_pass=True)
    assert ok2 is False

    # MDD worsens → FAIL
    ok3, _ = gfs.head_to_head_verdict(
        baseline_oos=baseline, gated_oos={"sharpe_ratio": 6.0,
                                           "max_drawdown_pct": 6.0},
        delta_min=0.5, gated_gate_pass=True)
    assert ok3 is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/backtest/test_gate_cli_regime_flag.py -v
```
Expected: FAIL — `load_gate_config` / `head_to_head_verdict` not in `gfs`.

- [ ] **Step 3: Extend the CLI**

In `scripts/gate_futures_strategy.py`, add two helper functions near the top of the file (after the existing imports):

```python
def load_gate_config(path: str):
    """Load a RegimeGate YAML config into a GateConfig dataclass."""
    from shared.strategy.gates.regime_gate import GateConfig
    data = yaml.safe_load(Path(path).read_text())
    return GateConfig(
        regime_percentile_max=float(data.get("regime_percentile_max", 80.0)),
        impact_score_max=int(data.get("impact_score_max", 70)),
        event_window_minutes=int(data.get("event_window_minutes", 15)),
        require_overnight_us_direction=bool(
            data.get("require_overnight_us_direction", False)),
        permissive_on_missing=bool(data.get("permissive_on_missing", True)),
    )


def head_to_head_verdict(
    baseline_oos: dict, gated_oos: dict, delta_min: float,
    gated_gate_pass: bool,
) -> tuple[bool, float]:
    """spec §8: PASS iff gated clears its own robust gate AND
    OOS Sharpe improves by >= delta_min AND MDD does not worsen.
    Returns (ok, delta_sharpe)."""
    delta = gated_oos.get("sharpe_ratio", -99.0) - baseline_oos.get(
        "sharpe_ratio", -99.0)
    mdd_ok = gated_oos.get("max_drawdown_pct", 1e9) <= baseline_oos.get(
        "max_drawdown_pct", 1e9)
    return (bool(gated_gate_pass) and (delta >= delta_min) and mdd_ok, delta)
```

Then extend `main()`'s argparse:

```python
ap.add_argument("--gate", default=None,
                help="path to RegimeGate YAML; if set, the engine is "
                     "wrapped with the gate during the run")
ap.add_argument("--head-to-head", action="store_true",
                help="run baseline (no gate) then gated; require Δ Sharpe "
                     "≥ --delta-sharpe AND no MDD worsening for PASS")
ap.add_argument("--delta-sharpe", type=float, default=0.5,
                help="spec §8 head-to-head margin (default 0.5)")
```

And thread the gate into `_run_backtest`:

```python
def _run_backtest(cfg: dict, df, bt_config: BacktestConfig, gate=None) -> dict:
    strategy = StrategyFactory.create(cfg)
    adapter = BacktestStrategyAdapter(strategy, cfg)
    engine = BacktestEngine(adapter, bt_config, gate=gate)
    return engine.run(df.copy()).to_metrics_dict()
```

In `main()`, instantiate the gate once and pass it to objective + OOS run. For `--head-to-head`, run the same Optuna search twice (one `_run_backtest(..., gate=None)`, one `_run_backtest(..., gate=gate)`); print both verdicts + Δ Sharpe + the head-to-head `PASS|FAIL` line.

Concrete head-to-head wiring inside `main()` (added after the existing study completes, replacing the current single-pass OOS section):

```python
if a.head_to_head and a.gate:
    # The Optuna study above is the BASELINE (no gate). Re-run with gate:
    gate_cfg = load_gate_config(a.gate)
    gate = _build_gate(gate_cfg, oos_df, opt_df)  # see Task 5 step 4

    def objective_gated(trial):
        params = suggest_params(trial, space)
        cfg = apply_params(base_cfg, params)
        m = _run_backtest(cfg, opt_df, bt_config, gate=gate)
        for k in ("profit_factor", "total_trades", "win_rate",
                  "total_return_pct", "max_drawdown_pct"):
            trial.set_user_attr(k, float(m.get(k, 0.0)))
        return objective_value(m, a.min_trades)

    study_gated = optuna.create_study(
        direction="maximize", sampler=TPESampler(seed=42),
        study_name=f"{a.strategy}_gate_GATED")
    study_gated.optimize(objective_gated, n_trials=a.trials)

    baseline_oos = _run_backtest(
        apply_params(base_cfg, study.best_params), oos_df, bt_config, gate=None)
    gated_oos = _run_backtest(
        apply_params(base_cfg, study_gated.best_params),
        oos_df, bt_config, gate=gate)

    rg_gated = rescoped_gate(study_gated, gated_oos)
    ok, delta = head_to_head_verdict(
        baseline_oos, gated_oos, a.delta_sharpe, rg_gated["pass"])
    print(
        f"baseline OOS: sharpe={baseline_oos.get('sharpe_ratio', 0):.4f} "
        f"mdd={baseline_oos.get('max_drawdown_pct', 0):.2f}%")
    print(
        f"gated    OOS: sharpe={gated_oos.get('sharpe_ratio', 0):.4f} "
        f"mdd={gated_oos.get('max_drawdown_pct', 0):.2f}%")
    print(f">>> HEAD-TO-HEAD: {'PASS' if ok else 'FAIL'} "
          f"(Δsharpe={delta:.3f} vs δ={a.delta_sharpe} | "
          f"gated_rescoped_pass={rg_gated['pass']})")
    return 0 if ok else 1
```

- [ ] **Step 4: Add `_build_gate(...)` for ClickHouse-backed inputs**

The gate needs concrete `latest_vol_at` / `events_within` / `macro_for`. Add a private builder (in the same file or a small new module `shared/strategy/gates/ch_inputs.py`) that:
- Pre-loads vol_forecasts rows for the full data window via one SELECT (`%(name)s` parameterized, `_ch_naive(...)` for `DateTime64`)
- Pre-loads event_scores rows similarly
- Calls `fetch_macro_history(...)` once over the data window for macro
- Wraps them in an object with the three duck-typed methods the gate expects

Skeleton (place in the script for now; refactor if reused by P2-③):

```python
class _CHInputs:
    def __init__(self, vol_rows, event_rows, macro_map):
        # vol_rows: sorted list of (asof_naive_utc, regime_percentile)
        # event_rows: sorted list of (asof_naive_utc, impact_score)
        # macro_map: dict[date, MacroSnapshot]
        self._vol = vol_rows
        self._events = event_rows
        self._macro = macro_map
    def latest_vol_at(self, ts):
        ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
        cand = [r for r in self._vol if r[0] <= ts_n]
        return cand[-1] if cand else None
    def events_within(self, ts, window_min):
        ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
        lo = ts_n - dt.timedelta(minutes=window_min)
        return [r for r in self._events if lo <= r[0] <= ts_n]
    def macro_for(self, date):
        snap = self._macro.get(date)
        return getattr(snap, "sp500_change_pct", None) if snap else None


def _build_gate(gate_cfg, oos_df, opt_df):
    import datetime as dt
    from shared.db.client import get_clickhouse_client
    from shared.db.config import ClickHouseConfig
    from shared.backtest.macro_history import fetch_macro_history
    from shared.strategy.gates.regime_gate import RegimeGate

    full = pd.concat([opt_df, oos_df]) if oos_df is not None else opt_df
    start = full["datetime"].min().to_pydatetime()
    end = full["datetime"].max().to_pydatetime()
    start_n = start.replace(tzinfo=None) if getattr(start, "tzinfo", None) else start
    end_n = end.replace(tzinfo=None) if getattr(end, "tzinfo", None) else end

    cli = get_clickhouse_client(ClickHouseConfig.from_env())
    vol = cli.execute(
        "SELECT asof, regime_percentile FROM kospi.vol_forecasts "
        "WHERE asof >= %(s)s AND asof < %(e)s ORDER BY asof",
        {"s": start_n, "e": end_n})
    ev = cli.execute(
        "SELECT asof, impact_score FROM kospi.event_scores "
        "WHERE asof >= %(s)s AND asof < %(e)s ORDER BY asof",
        {"s": start_n, "e": end_n})
    macro = fetch_macro_history(start.date(), end.date())
    return RegimeGate(gate_cfg, _CHInputs(vol, ev, macro))
```

- [ ] **Step 5: Run unit tests + smoke `--help`**

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/backtest/test_gate_cli_regime_flag.py -v
/home/deploy/project/kis_unified_sts/.venv/bin/python scripts/gate_futures_strategy.py --help
```
Expected: 3 passed; `--help` shows `--gate`, `--head-to-head`, `--delta-sharpe`.

- [ ] **Step 6: Commit**

```bash
git add scripts/gate_futures_strategy.py tests/unit/backtest/test_gate_cli_regime_flag.py
git commit -m "$(cat <<'EOF'
feat(backtest): gate runner --gate + --head-to-head (spec 2026-05-21 P1-③ T5)

--gate <yaml> wraps the engine with a RegimeGate; --head-to-head
runs baseline + gated through the same search; spec §8 PASS iff
gated rescoped-gate pass AND Δ Sharpe ≥ --delta-sharpe AND gated
MDD ≤ baseline MDD. CH-backed inputs builder reads vol_forecasts /
event_scores / macro_history once for the data window.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Config files (search space + gate default)

**Files:** Create `config/optuna/futures/bb_reversion_15m.yaml`, `config/gates/regime_gate_default.yaml`.

- [ ] **Step 1: Create the bb_reversion_15m search space**

Mirrors the in-Python search space at `scripts/probe_bb_reversion_15m_gate.py:110–133` (the operator-validated WF-bracketing ranges):

```yaml
# config/optuna/futures/bb_reversion_15m.yaml
# Robust-gate search space (spec 2026-05-21 P1-③).
# Ranges bracket the documented WF-optimal (bb 43/1.4/1.06, rsi 16/45/83,
# bw 0.003) per scripts/probe_bb_reversion_15m_gate.py:110-133.
search_space:
  entry.params.bb_period:         {type: int,   low: 20,   high: 60,   step: 2}
  entry.params.bb_std:            {type: float, low: 1.2,  high: 2.6}
  entry.params.bb_touch_buffer:   {type: float, low: 1.00, high: 1.10}
  entry.params.rsi_period:        {type: int,   low: 8,    high: 24}
  entry.params.rsi_oversold:      {type: int,   low: 30,   high: 50}
  entry.params.rsi_overbought:    {type: int,   low: 70,   high: 90}
  entry.params.min_bb_bandwidth:  {type: float, low: 0.001, high: 0.010}
# Reference only — passed via CLI args.
holdout_split: "2026-02-01"
min_trades: 50
```

(Note: `gate_futures_strategy.py::suggest_params` does not currently support `step`; if `step` is needed, omit the key — Optuna's continuous range is fine for the gate test. Confirm by reading the current `suggest_params` body before relying on `step`; if absent, remove the four `step:` entries above.)

- [ ] **Step 2: Create the default gate config**

```yaml
# config/gates/regime_gate_default.yaml
# Default RegimeGate config (spec 2026-05-21 P1-③).
# Units: regime_percentile is 0-100 (empirical CDF); impact_score is 0-100.
regime_percentile_max: 80.0          # block when predicted RV exceeds 80th pct of in-fit history
impact_score_max: 70                 # block when any event within window scores > 70
event_window_minutes: 15
require_overnight_us_direction: false # phase-1 keep off; revisit in P2-③
permissive_on_missing: true          # spec §9 — never silently block on missing data
```

- [ ] **Step 3: Commit**

```bash
git add config/optuna/futures/bb_reversion_15m.yaml config/gates/regime_gate_default.yaml
git commit -m "$(cat <<'EOF'
feat(config): bb_reversion_15m search space + regime gate default (P1-③ T6)

Search space mirrors the WF-validated ranges in
scripts/probe_bb_reversion_15m_gate.py:110-133. Gate config uses
natural units (regime_percentile 0-100, impact_score 0-100) per
spec §13 correction 3.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Run the head-to-head gate test + record verdict

**Files:** Create `reports/optuna/BB_REVERSION_15M_REGIME_GATE.md`. (Optionally append a brief cross-ref to `reports/optuna/FINDINGS.md` whichever way the verdict lands — mirrors yesterday's T6.)

Per the integrity rules from yesterday's T6: do NOT fabricate numbers; transcribe the actual `>>> HEAD-TO-HEAD` line verbatim from the real completed run; this is a long-running step (≥1 hour for 70+70 trials × ~40s/trial); use a background-survivable launcher.

- [ ] **Step 1: Coverage audit + (if needed) historical recompute**

```bash
cd /home/deploy/wt-futures-approach3-regime-gate
# Cover both halves of the dataset: train (in-sample optuna) + OOS
/home/deploy/project/kis_unified_sts/.venv/bin/python scripts/audit_forecast_coverage.py \
  --start 2026-02-01 --end 2026-04-24 \
  --expected-trading-minutes 24300 --min-coverage 0.90
```

Per §13 correction 5 the live retention is 90d so any pre-2026-02-21 row is evicted. If `vol_forecasts.total < 90% of expected`, run the recompute on the OOS window (train period stays PERMISSIVE):

```bash
/home/deploy/project/kis_unified_sts/.venv/bin/python scripts/forecasting/recompute_har_rv_historical.py \
  --train-start 2025-07-01 --train-end 2026-02-01 \
  --test-start 2026-02-01 --test-end 2026-04-24 \
  --cadence-minutes 15
```

Record the audit + recompute output (counts written) into a single log: `/tmp/wr_regime_gate_audit.log`.

- [ ] **Step 2: Launch the head-to-head gate run (background, survives turn limits)**

```bash
cd /home/deploy/wt-futures-approach3-regime-gate
nohup /home/deploy/project/kis_unified_sts/.venv/bin/python scripts/gate_futures_strategy.py \
  --strategy bb_reversion_15m \
  --data data/kospi200f_1m_ch_101S6000.csv \
  --space config/optuna/futures/bb_reversion_15m.yaml \
  --gate config/gates/regime_gate_default.yaml \
  --head-to-head --delta-sharpe 0.5 \
  --holdout-split 2026-02-01 --min-trades 50 --trials 70 \
  > /tmp/bb_regime_gate.log 2>&1 &
echo "launched PID $!"
```

(If `data/kospi200f_1m_ch_101S6000.csv` is absent in the worktree, `cp` it read-only from `/home/deploy/project/kis_unified_sts/data/` — same as yesterday's T6.)

Wait for completion via a waiter that returns when either the `>>> HEAD-TO-HEAD` line appears or the process exits:

```bash
until grep -q '>>> HEAD-TO-HEAD' /tmp/bb_regime_gate.log 2>/dev/null \
      || ! pgrep -f 'scripts/gate_futures_strategy.py' >/dev/null; do
  sleep 30
done
echo "=== DONE ==="; tail -25 /tmp/bb_regime_gate.log
```

- [ ] **Step 3: Capture the real numbers**

From `/tmp/bb_regime_gate.log` extract VERBATIM (no rounding-fraud, no softening):
- the `baseline OOS:` line
- the `gated    OOS:` line
- the `>>> HEAD-TO-HEAD:` line (PASS|FAIL + Δsharpe + δ)
- `study.best_params` for baseline and gated (printed by the existing CLI)

- [ ] **Step 4: Write the verdict report**

Create `reports/optuna/BB_REVERSION_15M_REGIME_GATE.md`. Fill bracketed values from the real run only:

```markdown
# bb_reversion_15m × RegimeGate — head-to-head verdict (2026-05-21)

Spec: docs/superpowers/specs/2026-05-21-futures-approach3-regime-gate-design.md (§7 robust gate, §8 head-to-head δ)
Tool: scripts/gate_futures_strategy.py --head-to-head --delta-sharpe 0.5
Data: data/kospi200f_1m_ch_101S6000.csv | holdout 2026-02-01 | min-trades 50 | 70 trials each
Gate config: config/gates/regime_gate_default.yaml (regime_percentile_max=80, impact_score_max=70, event_window=15min, permissive_on_missing=true)
Coverage: <transcribe the audit + recompute counts from /tmp/wr_regime_gate_audit.log>

## VERDICT: <PASS|FAIL>

`<paste the verbatim >>> HEAD-TO-HEAD line>`

| Metric | Baseline (no gate) | Gated (RegimeGate) | Δ |
|---|---|---|---|
| OOS Sharpe | `<x>` | `<y>` | `<y-x>` |
| OOS MDD %  | `<x>` | `<y>` | `<y-x>` |
| OOS Return %| `<x>` | `<y>` | `<y-x>` |
| OOS PF      | `<x>` | `<y>` | `<y-x>` |
| OOS Trades  | `<x>` | `<y>` | `<y-x>` |

best_params (baseline): `<study.best_params>`
best_params (gated):    `<study_gated.best_params>`
Raw log: /tmp/bb_regime_gate.log (ephemeral)

## Decision
<If PASS: "Spec §10 P2-③ trigger fires — apply RegimeGate to Setup A/C (separate spec/plan). gate_default.yaml is the operator-approved starting config; tightening/loosening is part of P2-③.">
<If FAIL: "Terminal for this gate variant. Spec §10 P3-③ trigger fires → tick/orderbook microstructure (was §3 ②, NEW spec). FINDINGS.md cross-ref appended. bb_reversion_15m baseline stays as-is in paper.">
```

- [ ] **Step 5: (FAIL branch only) append a cross-ref to FINDINGS.md**

If `>>> HEAD-TO-HEAD: FAIL`, append at the very end of `reports/optuna/FINDINGS.md` (do NOT rewrite):

```markdown

---

## bb_reversion_15m × RegimeGate — head-to-head (2026-05-21): FAIL (terminal)

`<paste the verbatim >>> HEAD-TO-HEAD line>`

RegimeGate (vol_forecasts + event_scores + macro_overnight) over
bb_reversion_15m did not clear spec §8 head-to-head (δ=0.5, MDD not
worsen). 70+70 trials, holdout 2026-02-01. Per spec §10 P3-③ trigger
fires → tick/orderbook microstructure (new spec). Full report:
reports/optuna/BB_REVERSION_15M_REGIME_GATE.md.
```

- [ ] **Step 6: Commit**

```bash
cd /home/deploy/wt-futures-approach3-regime-gate
git add reports/optuna/BB_REVERSION_15M_REGIME_GATE.md
# if FAIL only: git add reports/optuna/FINDINGS.md
git commit -m "$(cat <<'EOF'
docs(optuna): bb_reversion_15m × RegimeGate verdict (spec 2026-05-21 P1-③)

Head-to-head against baseline bb_reversion_15m: PASS→P2-③ apply gate
to Setup A/C / FAIL→P3-③ tick microstructure (new spec). Recorded
from the real completed run (no fabricated numbers).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review

**1. Spec coverage:**
- §4 P0-③ data audit → Task 1 ✅
- §6 C2 historical recompute → Task 2 (built unconditionally; T7-Step-1 decides invocation) ✅
- §6 C3 RegimeGate filter → Task 3 ✅
- §6 C4 engine-layer hook (§13 correction 2) → Task 4 ✅
- §6 C5 gate runner extension → Task 5 ✅
- §6 C6 decisive head-to-head + verdict → Task 6 (configs) + Task 7 (run + record) ✅
- §8 head-to-head δ + MDD-no-worsen → Task 5 `head_to_head_verdict` ✅
- §9 PERMISSIVE-degrade, look-ahead-safe, no live flags → Task 3 tests + Task 4 backward-compat ✅
- §10 P2-③/P3-③ trigger record → Task 7 Step 4/5 decision branches ✅
- §13 corrections recorded in spec → Task 0 ✅

**2. Placeholder scan:** No `TBD`/`TODO`. Bracketed values in Task 7 Step 4 are *run outputs to capture*, explicitly called out as such. Task 5 Step 3's note about `suggest_params` not yet supporting `step` is a precise instruction to verify-and-act, not a vague placeholder. Task 4 Step 3's reference to "exact variable names `timestamp`/`code`" is grounded in the verified `on_bar` region.

**3. Type/name consistency:** `GateConfig` (Task 3 module + Task 5 loader + Task 6 YAML), `RegimeGate.allow(ts, asset, signal_direction)` (Task 3 + Task 4 engine call site), `RECOMPUTE_MODEL_VERSION = "har_rv_v1_recompute"` (Task 2 + Task 1 audit's countIf + Task 5 _CHInputs reads neither tag — operates on all rows, neutral by design), `head_to_head_verdict(baseline_oos, gated_oos, delta_min, gated_gate_pass)` (Task 5 helper + test). `SignalType.HOLD` is the block path consistently (§13 correction 1). ✅

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-21-futures-approach3-regime-gate-p0-p1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, with two-stage review (spec compliance then code quality) between tasks. Same flow as yesterday's P0+P1 — through-and-out in this session.

**2. Inline Execution** — Execute tasks in this session with batched checkpoints for your review.

Which approach?
