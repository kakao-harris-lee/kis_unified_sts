"""Tests for HAR-RV model (Corsi 2009)."""
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from shared.forecasting.config import HARRVConfig
from shared.forecasting.volatility_har_rv import VolatilityForecaster


def _make_synthetic_rv_history(n_days: int, seed: int = 0) -> pd.Series:
    """Generate plausible daily RV series for testing. Mean ≈ 1e-4 (5% daily vol).

    Uses AR(1) on log-RV to mimic real-world volatility clustering (HAR-RV's
    raison d'être). Without persistence, OLS cannot predict iid noise and the
    OOS R² guard would always trip.
    """
    rng = np.random.default_rng(seed)
    phi = 0.90
    sigma = 0.05
    mu = np.log(1e-4)
    log_rv = np.empty(n_days)
    log_rv[0] = mu
    eps = rng.normal(0.0, sigma, size=n_days)
    for t in range(1, n_days):
        log_rv[t] = (1.0 - phi) * mu + phi * log_rv[t - 1] + eps[t]
    base = np.exp(log_rv)
    dates = pd.date_range("2026-01-01", periods=n_days, freq="B")
    return pd.Series(base, index=dates.date, name="rv")


def test_fit_with_sufficient_data_returns_finite_coefficients():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    assert f._coefficients is not None
    for coef in (f._coefficients.beta_0, f._coefficients.beta_d,
                  f._coefficients.beta_w, f._coefficients.beta_m):
        assert np.isfinite(coef)


def test_fit_with_insufficient_data_raises():
    cfg = HARRVConfig(history_days=22)
    history = _make_synthetic_rv_history(10)  # < 22 minimum
    f = VolatilityForecaster(cfg)
    with pytest.raises(ValueError, match="insufficient"):
        f.fit(history)


def test_fit_records_oos_r2_in_range():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    assert f._coefficients is not None
    assert -1.0 <= f._coefficients.r2_oos <= 1.0


def test_forecast_returns_positive_finite():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    asof = datetime.now(UTC)
    vf = f.forecast(asof, current_close=380.0)
    assert vf.forecast_pct > 0
    assert vf.forecast_atr_equivalent > 0
    assert np.isfinite(vf.forecast_pct)
    assert 0 <= vf.regime_percentile <= 100


def test_forecast_unit_conversion_atr_equivalent():
    """forecast_atr_equivalent ≈ forecast_pct × close × sqrt(15/(252*390)) / 100."""
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    vf = f.forecast(datetime.now(UTC), current_close=380.0)
    expected = vf.forecast_pct * 380.0 * np.sqrt(15 / (252 * 390)) / 100
    assert vf.forecast_atr_equivalent == pytest.approx(expected, rel=0.01)


def test_forecast_uses_loaded_coefficients():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    vf1 = f.forecast(datetime.now(UTC), current_close=380.0)
    # Force coefficients change — forecast should change
    f._coefficients.beta_d *= 2.0
    f._coefficients.beta_w *= 2.0
    f._coefficients.beta_m *= 2.0
    vf2 = f.forecast(datetime.now(UTC), current_close=380.0)
    assert vf2.forecast_pct != pytest.approx(vf1.forecast_pct)


def test_is_fit_stale_after_one_day():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    assert not f.is_fit_stale(now=datetime.now(UTC))
    f._last_fit_at = datetime.now(UTC) - timedelta(days=2)
    assert f.is_fit_stale(now=datetime.now(UTC))


def test_low_oos_r2_marks_model_as_low_quality():
    """If OOS R² < min_r2_oos, model should refuse to predict (raise)."""
    cfg = HARRVConfig(min_r2_oos=0.99)  # near-impossible
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    with pytest.raises(ValueError, match="R²"):
        f.fit(history)


def test_serialization_roundtrip():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    blob = f.to_json()
    f2 = VolatilityForecaster.from_json(blob, cfg)
    assert f2._coefficients is not None
    vf1 = f.forecast(datetime.now(UTC), current_close=380.0)
    vf2 = f2.forecast(datetime.now(UTC), current_close=380.0)
    assert vf2.forecast_pct == pytest.approx(vf1.forecast_pct)


def test_regime_percentile_calculation():
    cfg = HARRVConfig()
    history = _make_synthetic_rv_history(60)
    f = VolatilityForecaster(cfg)
    f.fit(history)
    # Force a very high RV component — percentile should be high
    f._latest_components = (1e-2, 1e-2, 1e-2)  # 10x mean
    vf = f.forecast(datetime.now(UTC), current_close=380.0)
    assert vf.regime_percentile > 90
