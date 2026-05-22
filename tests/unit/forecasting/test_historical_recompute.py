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


def test_load_candles_from_csv_returns_correct_shape(tmp_path):
    # Schema: datetime,open,high,low,close,volume  (no 'code')
    csv = tmp_path / "clean.csv"
    csv.write_text(
        "datetime,open,high,low,close,volume\n"
        "2025-08-01 09:00:00,400.0,400.5,399.5,400.2,150\n"
        "2025-08-01 09:01:00,400.2,400.4,400.0,400.3,200\n"
        "2025-08-04 09:00:00,401.0,401.2,400.8,401.1,180\n")
    df = hrr._load_candles_from_csv(str(csv), dt.date(2025, 8, 1), dt.date(2025, 8, 5))
    assert len(df) == 3
    # Same shape as _fetch_minute_candles output: UTC DatetimeIndex, OHLCV columns
    assert df.index.tz is not None  # tz-aware
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.iloc[0]["close"] == 400.2
    assert df.iloc[-1]["volume"] == 180


def test_load_candles_from_csv_respects_date_range(tmp_path):
    csv = tmp_path / "clean.csv"
    csv.write_text(
        "datetime,open,high,low,close,volume\n"
        "2025-07-31 15:30:00,395.0,395.0,395.0,395.0,10\n"  # before start → excluded
        "2025-08-01 09:00:00,400.0,400.5,399.5,400.2,150\n"  # included
        "2025-08-05 09:00:00,402.0,402.5,401.5,402.2,250\n"  # at end (exclusive) → excluded
        "2025-08-04 15:30:00,401.0,401.0,401.0,401.0,50\n")  # included
    df = hrr._load_candles_from_csv(str(csv), dt.date(2025, 8, 1), dt.date(2025, 8, 5))
    assert len(df) == 2
    closes = df["close"].tolist()
    assert 400.2 in closes
    assert 401.0 in closes
    assert 395.0 not in closes
    assert 402.2 not in closes


def test_load_candles_from_csv_empty_window_returns_empty_df(tmp_path):
    csv = tmp_path / "clean.csv"
    csv.write_text(
        "datetime,open,high,low,close,volume\n"
        "2025-08-01 09:00:00,400.0,400.5,399.5,400.2,150\n")
    df = hrr._load_candles_from_csv(str(csv), dt.date(2026, 1, 1), dt.date(2026, 1, 5))
    assert len(df) == 0
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_rolling_components_produce_varying_labels(monkeypatch):
    """With full_rv supplied, _latest_components updates per OOS day → labels vary.
    Regression for T7 degenerate-labels FAIL (all labels = 34.03 constant)."""
    # Synthetic train (200 days, spread across a range) so that OOS preds land at
    # different percentiles within the training distribution.
    import numpy as np
    rng = pd.date_range("2025-04-01", periods=200, freq="D")
    # Train: linearly varying RV from 1e-4 to 1e-2 so percentile computation is fine
    train_vals = np.linspace(1e-4, 1e-2, len(rng))
    train_rv = pd.Series(train_vals, index=rng.date)
    # OOS: 10 days with gradually increasing RV — stays within train range so pred_rv
    # lands at different internal percentiles, not all clamped to 0/100.
    oos = pd.date_range("2025-10-20", periods=10, freq="D")
    oos_vals = np.linspace(1e-3, 8e-3, 10)       # rising, within training range
    full_rv = pd.concat([train_rv, pd.Series(oos_vals, index=oos.date)])

    rows_written = []
    def fake_insert(client, rows):
        rows_written.extend(rows)
        return len(rows)
    monkeypatch.setattr(hrr, "_insert_rows", fake_insert)

    # One 15-min stamp per OOS day at 09:00
    test_minutes = pd.DatetimeIndex([
        pd.Timestamp(d.year, d.month, d.day, 9, 0) for d in oos.date])
    hrr.recompute_and_insert(
        train_rv=train_rv, test_minutes=test_minutes,
        current_close=380.0, client=None, full_rv=full_rv)
    assert len(rows_written) == 10
    # regime_percentile is the 5th tuple element
    percentiles = [r[4] for r in rows_written]
    # Labels MUST vary — the rolling components update per day → pred_rv shifts
    # The key assertion: labels are NOT all identical (the pre-fix constant=34.03 bug)
    assert len(set(percentiles)) > 1, (
        f"labels degenerate (all identical): {percentiles}")
    # Max should exceed min by a meaningful margin (the synthetic OOS rises stair-step)
    assert max(percentiles) - min(percentiles) >= 20.0, (
        f"labels too clustered: range {max(percentiles)-min(percentiles):.1f}")


def test_full_rv_none_preserves_frozen_components(monkeypatch):
    """Backward-compat: full_rv=None → _latest_components stays frozen → constant
    labels (the pre-fix behavior). Existing T2 tests already cover the float-path
    happy case; this test pins that no behavior change happens when full_rv is omitted."""
    rng = pd.date_range("2025-09-01", periods=90, freq="D")
    rv = pd.Series(0.0001 + 1e-6 * (rng.dayofyear % 7), index=rng.date)
    rows_written = []
    def fake_insert(client, rows):
        rows_written.extend(rows)
        return len(rows)
    monkeypatch.setattr(hrr, "_insert_rows", fake_insert)
    test_minutes = pd.date_range("2025-12-01 09:00", "2025-12-01 09:45", freq="15min")
    # No full_rv kwarg — backward-compat path
    hrr.recompute_and_insert(
        train_rv=rv, test_minutes=test_minutes, current_close=380.0, client=None)
    percentiles = [r[4] for r in rows_written]
    # All 4 forecasts on the SAME day with frozen components → SAME label
    assert len(set(percentiles)) == 1, (
        f"backward-compat broken: labels vary when full_rv=None: {percentiles}")
