"""Standard-correctness tests for ``shared.indicators.reference``."""

import math

import numpy as np
import pandas as pd
import pytest

from shared.indicators.momentum import RSICalculator
from shared.indicators.reference import (
    ADXCalculator,
    ATRCalculator,
    StochRSICalculator,
    wilder_rma,
    wilder_rsi,
)
from shared.indicators.streaming.calculations import IndicatorCalculationMixin
from shared.indicators.streaming.candles import Candle

pytestmark = pytest.mark.unit


_N_BARS = 64


def _build_ohlcv() -> dict[str, list[float]]:
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    volumes: list[float] = []
    for i in range(_N_BARS):
        close = 100.0 + 0.12 * i + 4.0 * math.sin(i / 4.0) + 1.5 * math.cos(i / 2.3)
        span = 0.8 + 0.5 * abs(math.sin(i / 3.0))
        high = close + span
        low = close - span * (0.7 + 0.3 * abs(math.cos(i / 5.0)))
        open_ = close - 0.4 * math.sin(i / 2.0)
        high = max(high, open_, close)
        low = min(low, open_, close)
        volume = 2000.0 + 900.0 * abs(math.sin(i / 2.5)) + 15.0 * i
        opens.append(open_)
        highs.append(high)
        lows.append(low)
        closes.append(close)
        volumes.append(volume)
    return {
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    }


@pytest.fixture(scope="module")
def ohlcv() -> dict[str, list[float]]:
    return _build_ohlcv()


@pytest.fixture
def frame(ohlcv: dict[str, list[float]]) -> pd.DataFrame:
    """Fresh DataFrame per test (calculators mutate the input frame)."""
    return pd.DataFrame(ohlcv)


_ADX_REF = 31.634448
_ADX_RUNTIME_WILDER = 31.719136

_STOCHRSI_K = 11.901304
_STOCHRSI_D = 35.748708
_STOCHRSI_K_PREV = 33.286079

_RSI_WILDER = 47.099143

_TOL = 5e-3


def test_wilder_rma_seed_and_recursion() -> None:
    """RMA seeds at index period-1 with the SMA, then applies Wilder recursion."""
    vals = np.arange(1, 11, dtype=float)
    out = wilder_rma(vals, period=3)

    assert np.isnan(out[0]) and np.isnan(out[1])
    assert out[2] == pytest.approx(2.0, abs=1e-12)
    assert out[3] == pytest.approx((2.0 * 2 + 4.0) / 3.0, abs=1e-12)


def test_wilder_rsi_matches_shared_rsicalculator(frame: pd.DataFrame) -> None:
    """Reference Wilder RSI == shared RSICalculator on the last (non-warmup) bar."""
    ref = wilder_rsi(frame["close"], period=14)
    shared = RSICalculator(period=14).calculate(frame.copy())["rsi"]

    ref_last = float(ref.iloc[-1])
    shared_last = float(shared.iloc[-1])

    assert ref_last == pytest.approx(shared_last, abs=1e-9)
    assert ref_last == pytest.approx(_RSI_WILDER, abs=_TOL)
    assert np.isnan(ref.iloc[0])


def test_adx_range_and_snapshot(frame: pd.DataFrame) -> None:
    """Reference ADX is in [0, 100] and matches its deterministic snapshot."""
    out = ADXCalculator(period=14).calculate(frame)
    adx = out["adx"].dropna()

    assert (adx >= 0.0).all() and (adx <= 100.0).all()
    assert float(adx.iloc[-1]) == pytest.approx(_ADX_REF, abs=_TOL)


def test_adx_calculate_last_matches_series(ohlcv: dict[str, list[float]]) -> None:
    """The scalar convenience equals the last non-NaN value of the series form."""
    calc = ADXCalculator(period=14)
    scalar = calc.calculate_last(
        np.asarray(ohlcv["high"]),
        np.asarray(ohlcv["low"]),
        np.asarray(ohlcv["close"]),
    )
    series_last = float(calc.calculate(pd.DataFrame(ohlcv))["adx"].dropna().iloc[-1])
    assert scalar is not None
    assert scalar == pytest.approx(series_last, abs=1e-12)


def test_adx_is_wilder_smoothed_not_raw_dx(frame: pd.DataFrame) -> None:
    """ADX is a Wilder-smoothing of DX -> markedly smoother than the DX series."""
    out = ADXCalculator(period=14).calculate(frame)
    adx = out["adx"].dropna().to_numpy()
    dx = out["dx"].dropna().to_numpy()

    adx_step_vol = float(np.std(np.diff(adx)))
    dx_step_vol = float(np.std(np.diff(dx)))

    assert adx_step_vol < 0.5 * dx_step_vol


def test_adx_reference_close_to_runtime_canonical_wilder(frame: pd.DataFrame) -> None:
    """Reference ADX agrees with the runtime canonical Wilder ADX."""
    adx_ref = float(ADXCalculator(period=14).calculate(frame)["adx"].dropna().iloc[-1])
    assert adx_ref == pytest.approx(_ADX_RUNTIME_WILDER, abs=0.5)


def test_adx_flat_market_is_zero() -> None:
    """A perfectly flat market has no directional movement -> ADX 0 (or NaN)."""
    flat = pd.DataFrame(
        {
            "high": [100.0] * 40,
            "low": [100.0] * 40,
            "close": [100.0] * 40,
        }
    )
    out = ADXCalculator(period=14).calculate(flat)
    adx = out["adx"].dropna()
    if not adx.empty:
        assert float(adx.iloc[-1]) == pytest.approx(0.0, abs=1e-9)


def test_stochrsi_range_invariant(frame: pd.DataFrame) -> None:
    """Raw StochRSI, %K, and %D all live in [0, 100]."""
    out = StochRSICalculator().calculate(frame)
    for col in ("stochrsi", "stochrsi_k", "stochrsi_d"):
        series = out[col].dropna()
        assert (series >= 0.0).all() and (series <= 100.0).all()


def test_stochrsi_value_snapshot(frame: pd.DataFrame) -> None:
    """Last-bar %K/%D match deterministic snapshots."""
    out = StochRSICalculator().calculate(frame)
    assert float(out["stochrsi_k"].dropna().iloc[-1]) == pytest.approx(
        _STOCHRSI_K, abs=_TOL
    )
    assert float(out["stochrsi_d"].dropna().iloc[-1]) == pytest.approx(
        _STOCHRSI_D, abs=_TOL
    )


def test_stochrsi_d_is_smoothing_of_k(frame: pd.DataFrame) -> None:
    """%D equals the trailing SMA of %K over d_period (smoothing relationship)."""
    calc = StochRSICalculator(k_period=3, d_period=3)
    out = calc.calculate(frame)
    k = out["stochrsi_k"]
    d = out["stochrsi_d"]

    expected_d = float(k.iloc[-3:].mean())
    assert float(d.iloc[-1]) == pytest.approx(expected_d, abs=1e-9)


def test_stochrsi_latest_values_emits_strategy_keys(frame: pd.DataFrame) -> None:
    """``latest_values`` emits exactly the flat keys StochRSITrendEntry reads."""
    calc = StochRSICalculator()
    out = calc.calculate(frame.copy())
    values = calc.latest_values(frame.copy())

    assert set(values) == {"stochrsi_k", "stochrsi_d", "stochrsi_k_prev"}
    assert values["stochrsi_k"] == pytest.approx(_STOCHRSI_K, abs=_TOL)
    assert values["stochrsi_d"] == pytest.approx(_STOCHRSI_D, abs=_TOL)
    assert values["stochrsi_k_prev"] == pytest.approx(_STOCHRSI_K_PREV, abs=_TOL)
    assert values["stochrsi_k_prev"] == pytest.approx(
        float(out["stochrsi_k"].iloc[-2]), abs=1e-9
    )


def test_stochrsi_latest_values_neutral_when_insufficient() -> None:
    """With too little data, ``latest_values`` falls back to the neutral 50."""
    short = pd.DataFrame({"close": [100.0, 101.0, 100.5]})
    values = StochRSICalculator().latest_values(short)
    assert values == {
        "stochrsi_k": 50.0,
        "stochrsi_d": 50.0,
        "stochrsi_k_prev": 50.0,
    }


def test_stochrsi_flat_market_is_neutral() -> None:
    """A flat RSI window (max == min) normalizes to the neutral 50, not NaN/inf."""
    flat = pd.DataFrame({"close": [100.0] * 40})
    out = StochRSICalculator().calculate(flat)
    raw = out["stochrsi"].dropna()
    assert not raw.empty
    assert np.allclose(raw.to_numpy(), 50.0, atol=1e-9)


@pytest.fixture
def candles(ohlcv: dict[str, list[float]]) -> list[Candle]:
    """Runtime Candle list for cross-checking against the streaming ATR."""
    return [
        Candle(
            open=ohlcv["open"][i],
            high=ohlcv["high"][i],
            low=ohlcv["low"][i],
            close=ohlcv["close"][i],
            volume=ohlcv["volume"][i],
            minute=930 + i,
        )
        for i in range(_N_BARS)
    ]


def test_atr_true_range_is_max_of_three(ohlcv: dict[str, list[float]]) -> None:
    """TR[i] = max(H-L, |H-Cp|, |L-Cp|); TR aligned to bars 1..n-1 (bar 0 has no Cp)."""
    high = np.asarray(ohlcv["high"])
    low = np.asarray(ohlcv["low"])
    close = np.asarray(ohlcv["close"])
    tr = ATRCalculator.true_range(high, low, close)
    assert tr.shape[0] == high.shape[0] - 1
    i = 10
    expected = max(
        high[i + 1] - low[i + 1],
        abs(high[i + 1] - close[i]),
        abs(low[i + 1] - close[i]),
    )
    assert tr[i] == pytest.approx(expected, abs=1e-9)


def test_atr_sma_mode_matches_runtime_calc_atr_raw(
    ohlcv: dict[str, list[float]], candles: list[Candle]
) -> None:
    """SMA mode reproduces the runtime standalone ATR exactly -> safe drop-in."""
    atr_ref = ATRCalculator(period=14, mode="sma").atr_last(
        ohlcv["high"], ohlcv["low"], ohlcv["close"]
    )
    atr_runtime = IndicatorCalculationMixin._calc_atr_raw(candles, period=14)
    assert atr_ref is not None
    assert atr_ref == pytest.approx(atr_runtime, abs=1e-9)


def test_atr_wilder_mode_matches_wilder_rma_of_true_range(
    ohlcv: dict[str, list[float]],
) -> None:
    """Wilder mode == wilder_rma(TR) -- the same ATR the reference ADX smooths."""
    high = np.asarray(ohlcv["high"])
    low = np.asarray(ohlcv["low"])
    close = np.asarray(ohlcv["close"])
    tr = ATRCalculator.true_range(high, low, close)
    expected = wilder_rma(tr, 14)
    expected_last = float(expected[~np.isnan(expected)][-1])

    atr_ref = ATRCalculator(period=14, mode="wilder").atr_last(
        ohlcv["high"], ohlcv["low"], ohlcv["close"]
    )
    assert atr_ref == pytest.approx(expected_last, abs=1e-9)


def test_atr_wilder_and_sma_modes_diverge(ohlcv: dict[str, list[float]]) -> None:
    """The two smoothings genuinely differ -- the SoT divergence this consolidates."""
    sma = ATRCalculator(period=14, mode="sma").atr_last(
        ohlcv["high"], ohlcv["low"], ohlcv["close"]
    )
    wil = ATRCalculator(period=14, mode="wilder").atr_last(
        ohlcv["high"], ohlcv["low"], ohlcv["close"]
    )
    assert sma is not None and wil is not None
    assert sma > 0.0 and wil > 0.0
    assert abs(sma - wil) > 1e-6


def test_atr_series_warmup_is_nan_and_causal(frame: pd.DataFrame) -> None:
    """calculate() adds an ``atr`` column with NaN warmup; first valid at index period."""
    out = ATRCalculator(period=14, mode="sma").calculate(frame)
    atr = out["atr"].to_numpy()
    assert np.isnan(atr[:14]).all(), "bars before a full TR window must be NaN"
    assert not np.isnan(atr[14]), "first ATR available once `period` TRs exist"


def test_atr_fraction_last_is_atr_over_close(ohlcv: dict[str, list[float]]) -> None:
    """atr_fraction_last returns atr_last / last_close (an explicit fraction, not %)."""
    calc = ATRCalculator(period=14, mode="sma")
    atr = calc.atr_last(ohlcv["high"], ohlcv["low"], ohlcv["close"])
    frac = calc.atr_fraction_last(ohlcv["high"], ohlcv["low"], ohlcv["close"])
    assert atr is not None and frac is not None
    assert frac == pytest.approx(atr / ohlcv["close"][-1], abs=1e-12)


def test_atr_insufficient_data_returns_none() -> None:
    calc = ATRCalculator(period=14, mode="sma")
    assert calc.atr_last([100.0, 101.0], [99.0, 100.0], [99.5, 100.5]) is None


def test_atr_invalid_mode_rejected() -> None:
    with pytest.raises(ValueError):
        ATRCalculator(period=14, mode="ewm")
