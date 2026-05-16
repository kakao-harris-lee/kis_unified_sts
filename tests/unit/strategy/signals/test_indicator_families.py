from shared.strategy.signals.indicator_families import (
    momentum_reversal_score,
    trend_breakout_score,
    volatility_regime_magnitude,
    volume_microstructure_score,
)


def test_momentum_missing_inputs_neutral():
    assert momentum_reversal_score({}) == 0.0


def test_momentum_oversold_is_long_positive():
    ind = {"momentum_5m": {"rsi": 10.0, "williams_r": -95.0, "sto_k": 5.0}}
    s = momentum_reversal_score(ind)
    assert 0.5 < s <= 1.0  # deep oversold → strong long-reversal


def test_momentum_overbought_is_short_negative():
    ind = {"momentum_5m": {"rsi": 90.0, "williams_r": -5.0, "sto_k": 95.0}}
    assert -1.0 <= momentum_reversal_score(ind) < -0.5


def test_trend_missing_neutral():
    assert trend_breakout_score({}) == 0.0


def test_trend_up_alignment_positive():
    ind = {"ema_5": 102.0, "ema_20": 100.0, "adx": 40.0,
           "vwap": 99.0, "close": 103.0}
    assert trend_breakout_score(ind) > 0.4


def test_trend_down_alignment_negative():
    ind = {"ema_5": 98.0, "ema_20": 100.0, "adx": 40.0,
           "vwap": 101.0, "close": 97.0}
    assert trend_breakout_score(ind) < -0.4


def test_trend_weak_adx_damped():
    strong = {"ema_5": 102.0, "ema_20": 100.0, "adx": 50.0,
              "vwap": 99.0, "close": 103.0}
    weak = {"ema_5": 102.0, "ema_20": 100.0, "adx": 5.0,
            "vwap": 99.0, "close": 103.0}
    assert abs(trend_breakout_score(weak)) < abs(trend_breakout_score(strong))


def test_volume_missing_neutral():
    assert volume_microstructure_score({}) == 0.0


def test_volume_up_flow_positive():
    ind = {"volume_velocity": 0.8, "rvol": 2.0, "vwap": 100.0,
           "close": 101.0}
    assert volume_microstructure_score(ind) > 0.3


def test_volume_low_rvol_damped():
    hi = {"volume_velocity": 0.8, "rvol": 2.0, "vwap": 100.0, "close": 101.0}
    lo = {"volume_velocity": 0.8, "rvol": 0.2, "vwap": 100.0, "close": 101.0}
    assert abs(volume_microstructure_score(lo)) < abs(
        volume_microstructure_score(hi))


def test_vol_regime_missing_is_zero():
    assert volatility_regime_magnitude({}, None) == 0.0


def test_vol_regime_from_forecast_percentile():
    class _VF:
        regime_percentile = 80.0

    assert volatility_regime_magnitude({}, _VF()) == 0.8


def test_vol_regime_atr_fallback_when_no_forecast():
    ind = {"atr": 2.0, "close": 100.0}  # atr/close = 2% → high
    m = volatility_regime_magnitude(ind, None)
    assert 0.0 < m <= 1.0
