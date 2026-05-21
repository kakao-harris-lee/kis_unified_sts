import datetime as dt
import importlib.util
import pathlib

import pandas as pd
import pytest

_REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "hrr", _REPO / "scripts" / "forecasting" / "recompute_har_rv_historical.py")
hrr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hrr)


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


def test_lookahead_guard_rejects_equal_dates():
    with pytest.raises(ValueError, match="overlap"):
        hrr._validate_split(
            train_end=dt.date(2026, 2, 1), test_start=dt.date(2026, 2, 1))


def test_fit_then_apply_produces_rows_at_15min_cadence(monkeypatch):
    # Tiny synthetic RV series + dummy fit, then apply over 1h test window
    rng = pd.date_range("2025-09-01", periods=90, freq="D")
    rv = pd.Series(0.0001 + 1e-6 * (rng.dayofyear % 7), index=rng.date)
    rows_written = []

    def fake_insert(client, rows):
        rows_written.extend(rows)
        return len(rows)

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


def test_callable_current_close_invoked_per_timestamp(monkeypatch):
    rng = pd.date_range("2025-09-01", periods=90, freq="D")
    rv = pd.Series(0.0001 + 1e-6 * (rng.dayofyear % 7), index=rng.date)
    rows_written = []
    captured_calls = []
    def fake_insert(client, rows):
        rows_written.extend(rows)
        return len(rows)
    monkeypatch.setattr(hrr, "_insert_rows", fake_insert)
    def cc(asof):
        captured_calls.append(asof)
        return 380.0 + len(captured_calls)
    test_idx = pd.date_range("2025-12-01 09:00", "2025-12-01 09:45", freq="15min")
    hrr.recompute_and_insert(train_rv=rv, test_minutes=test_idx,
                             current_close=cc, client=None)
    assert len(captured_calls) == 4  # 09:00, 09:15, 09:30, 09:45
    # Each row's forecast_atr_equivalent should differ since close varies per-call
    atrs = [r[3] for r in rows_written]
    assert len(set(atrs)) == 4
