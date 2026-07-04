"""Standard-correctness tests for ``shared.indicators.reference``.

These tests pin the *reference* (standard-accurate) calculators against known,
deterministic inputs and cross-check them against the existing established
standards in the repo:

    * ADX  -- canonical Wilder-smoothed ADX; proven to (a) sit in [0, 100],
      (b) be much smoother than the raw DX series, and (c) diverge sharply from
      the defective ``adaptive_detector._calc_adx`` (single, SMA-smoothed DX).
    * Bollinger -- ``ddof`` knob reproduces the repo convention (ddof=1) exactly
      (matches runtime ``_calc_bb``), and differs from population std (ddof=0).
    * StochRSI  -- values in [0, 100], correct K/D smoothing relationship, and a
      ``latest_values`` dict carrying exactly the flat keys the strategy needs.

Input generation mirrors ``tests/unit/indicators/test_calc_parity.py``: pure
closed-form OHLCV, no RNG, so the snapshot constants are permanently stable
across numpy/pandas versions.
"""

import math

import numpy as np
import pandas as pd
import pytest

# Target (read/import only)
from shared.indicators.momentum import RSICalculator
from shared.indicators.reference import (
    ADXCalculator,
    BollingerBandsCalculator,
    StochRSICalculator,
    wilder_rma,
    wilder_rsi,
)
from shared.regime.adaptive_detector import AdaptiveRegimeDetector

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Deterministic OHLCV sample (RNG-free -- identical generator to the parity harness)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Snapshot constants (deterministic; documented cross-checks)
# ---------------------------------------------------------------------------

# ADX: reference (canonical Wilder) vs runtime canonical Wilder vs detector DX.
_ADX_REF = 31.634448  # reference series/scalar
_ADX_RUNTIME_WILDER = 31.719136  # from test_calc_parity (runtime _calc_adx)
# M2 (2026-07-04): detector._calc_adx now delegates to ADXCalculator, so it
# yields the canonical Wilder ADX (== _ADX_REF) instead of the old defective
# single-bar DX (15.873272).
_ADX_DETECTOR_WILDER = 31.634448  # was 15.873272 (defective single-bar DX)

# Bollinger (last bar).
_BB_LOWER_DDOF1 = 99.902454
_BB_MID = 107.210789
_BB_UPPER_DDOF1 = 114.519124
_BB_LOWER_DDOF0 = 100.087505
_BB_UPPER_DDOF0 = 114.334073
_BB_BANDWIDTH = 0.136336
_BB_PERCENT_B = 0.447245

# StochRSI (last bar) + prior-bar %K.
_STOCHRSI_K = 11.901304
_STOCHRSI_D = 35.748708
_STOCHRSI_K_PREV = 33.286079

# Wilder RSI last bar -- must equal shared RSICalculator (== _RSI_SHARED_WILDER).
_RSI_WILDER = 47.099143

_TOL = 5e-3


# ---------------------------------------------------------------------------
# 0) Wilder primitives
# ---------------------------------------------------------------------------


def test_wilder_rma_seed_and_recursion() -> None:
    """RMA seeds at index period-1 with the SMA, then applies Wilder recursion."""
    vals = np.arange(1, 11, dtype=float)  # 1..10
    out = wilder_rma(vals, period=3)

    # indices 0,1 are warmup (NaN)
    assert np.isnan(out[0]) and np.isnan(out[1])
    # seed = mean(1,2,3) = 2.0
    assert out[2] == pytest.approx(2.0, abs=1e-12)
    # next = (2*2 + 4)/3 = 8/3
    assert out[3] == pytest.approx((2.0 * 2 + 4.0) / 3.0, abs=1e-12)


def test_wilder_rsi_matches_shared_rsicalculator(frame: pd.DataFrame) -> None:
    """Reference Wilder RSI == shared RSICalculator on the last (non-warmup) bar.

    This ties the reference layer to the already-established shared RSI standard
    (Wilder EMA), the one the M1 parity harness certified against pandas-ta.
    """
    ref = wilder_rsi(frame["close"], period=14)
    shared = RSICalculator(period=14).calculate(frame.copy())["rsi"]

    ref_last = float(ref.iloc[-1])
    shared_last = float(shared.iloc[-1])

    assert ref_last == pytest.approx(shared_last, abs=1e-9)
    assert ref_last == pytest.approx(_RSI_WILDER, abs=_TOL)
    # Warmup is preserved as NaN (unlike the strategy-path neutral-50 fill).
    assert np.isnan(ref.iloc[0])


# ---------------------------------------------------------------------------
# 1) ADX -- canonical Wilder vs defective detector DX
# ---------------------------------------------------------------------------


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
    """ADX is a Wilder-smoothing of DX -> markedly smoother than the DX series.

    The defining property of ADX (vs the detector's single DX) is the second
    Wilder-smoothing step. We assert the ADX first-difference volatility is a
    small fraction of the DX first-difference volatility.
    """
    out = ADXCalculator(period=14).calculate(frame)
    adx = out["adx"].dropna().to_numpy()
    dx = out["dx"].dropna().to_numpy()

    adx_step_vol = float(np.std(np.diff(adx)))
    dx_step_vol = float(np.std(np.diff(dx)))

    assert adx_step_vol < 0.5 * dx_step_vol


def test_adx_reference_close_to_runtime_canonical_wilder(frame: pd.DataFrame) -> None:
    """Reference ADX agrees with the runtime canonical Wilder ADX.

    Both are legitimate Wilder ADX; they differ only by a small warmup-seed
    offset (the runtime reports the first DI one bar after the seed). The gap is
    < 0.5 on this 64-bar sample and shrinks with more history -- far tighter than
    the ~16-point gap to the detector's single DX (next test).
    """
    adx_ref = float(ADXCalculator(period=14).calculate(frame)["adx"].dropna().iloc[-1])
    assert adx_ref == pytest.approx(_ADX_RUNTIME_WILDER, abs=0.5)


def test_adx_reference_agrees_with_detector_after_delegation(
    frame: pd.DataFrame, ohlcv: dict[str, list[float]]
) -> None:
    """Reference Wilder ADX now AGREES with ``detector._calc_adx`` (M2).

    ``adaptive_detector._calc_adx`` used to be named ADX but returned a single,
    SMA-smoothed DX (no directional-movement rule, no final DX smoothing),
    yielding ~15.9 vs the correct Wilder ADX ~31.6 -- under-reporting trend
    strength by roughly half. It now delegates to ``ADXCalculator``, so the two
    are the same value. If this ever diverges again (> 1e-6) the detector has
    stopped delegating or a third ADX has been reintroduced.
    """
    adx_ref = float(ADXCalculator(period=14).calculate(frame)["adx"].dropna().iloc[-1])

    detector = AdaptiveRegimeDetector()
    detector_adx = float(
        detector._calc_adx(
            np.asarray(ohlcv["high"]),
            np.asarray(ohlcv["low"]),
            np.asarray(ohlcv["close"]),
            period=14,
        )
    )

    assert detector_adx == pytest.approx(_ADX_DETECTOR_WILDER, abs=_TOL)
    # Exact delegation: detector == reference calculate_last (same code path).
    assert detector_adx == pytest.approx(adx_ref, abs=1e-9)


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


# ---------------------------------------------------------------------------
# 2) Bollinger -- ddof knob
# ---------------------------------------------------------------------------


def test_bollinger_ddof1_snapshot_and_ordering(frame: pd.DataFrame) -> None:
    """Default (ddof=1) reproduces the repo convention with correct ordering."""
    out = BollingerBandsCalculator(period=20, num_std=2.0, ddof=1).calculate(frame)
    lower = float(out["bb_lower"].iloc[-1])
    mid = float(out["bb_middle"].iloc[-1])
    upper = float(out["bb_upper"].iloc[-1])

    assert lower < mid < upper
    assert lower == pytest.approx(_BB_LOWER_DDOF1, abs=_TOL)
    assert mid == pytest.approx(_BB_MID, abs=_TOL)
    assert upper == pytest.approx(_BB_UPPER_DDOF1, abs=_TOL)


def test_bollinger_matches_runtime_calc_bb(
    frame: pd.DataFrame, ohlcv: dict[str, list[float]]
) -> None:
    """Reference BB (ddof=1) matches runtime ``_calc_bb`` (also ddof=1).

    A ``must-agree`` pair: both use period=20, num_std=2.0, sample std. This
    proves the reference is a drop-in for the runtime Bollinger convention.
    """
    from services.trading.indicator_calculations import IndicatorCalculationMixin

    class _Host(IndicatorCalculationMixin):
        def __init__(self) -> None:
            self.bb_period = 20
            self.bb_std = 2.0
            self.rsi_period = 14

    rt_lower, rt_mid, rt_upper = _Host()._calc_bb(ohlcv["close"])

    out = BollingerBandsCalculator(period=20, num_std=2.0, ddof=1).calculate(frame)
    assert float(out["bb_lower"].iloc[-1]) == pytest.approx(rt_lower, abs=1e-6)
    assert float(out["bb_middle"].iloc[-1]) == pytest.approx(rt_mid, abs=1e-6)
    assert float(out["bb_upper"].iloc[-1]) == pytest.approx(rt_upper, abs=1e-6)


def test_bollinger_ddof0_differs_from_ddof1(ohlcv: dict[str, list[float]]) -> None:
    """Population std (ddof=0) yields tighter bands and is distinct from ddof=1."""
    out0 = BollingerBandsCalculator(period=20, num_std=2.0, ddof=0).calculate(
        pd.DataFrame(ohlcv)
    )
    lower0 = float(out0["bb_lower"].iloc[-1])
    upper0 = float(out0["bb_upper"].iloc[-1])

    assert lower0 == pytest.approx(_BB_LOWER_DDOF0, abs=_TOL)
    assert upper0 == pytest.approx(_BB_UPPER_DDOF0, abs=_TOL)
    # ddof=0 bands are strictly inside ddof=1 bands (population std < sample std).
    assert lower0 > _BB_LOWER_DDOF1
    assert upper0 < _BB_UPPER_DDOF1


def test_bollinger_ratio_features(frame: pd.DataFrame) -> None:
    """Bandwidth and %B are emitted and take sane, snapshot-stable values."""
    out = BollingerBandsCalculator(period=20, num_std=2.0, ddof=1).calculate(frame)
    bandwidth = float(out["bb_bandwidth"].iloc[-1])
    percent_b = float(out["bb_percent_b"].iloc[-1])

    assert bandwidth > 0.0
    assert bandwidth == pytest.approx(_BB_BANDWIDTH, abs=_TOL)
    assert percent_b == pytest.approx(_BB_PERCENT_B, abs=_TOL)
    # %B in [0, 1] means price is inside the bands (true for this sample).
    assert 0.0 <= percent_b <= 1.0


def test_bollinger_warmup_is_nan(frame: pd.DataFrame) -> None:
    """Rows before a full window are NaN (min_periods=period, no partial bands)."""
    out = BollingerBandsCalculator(period=20).calculate(frame)
    assert out["bb_middle"].iloc[:19].isna().all()
    assert not math.isnan(out["bb_middle"].iloc[19])


# ---------------------------------------------------------------------------
# 3) StochRSI -- the missing producer
# ---------------------------------------------------------------------------


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

    # Last %D == mean of last 3 %K (min_periods=1 -> full window at the tail).
    expected_d = float(k.iloc[-3:].mean())
    assert float(d.iloc[-1]) == pytest.approx(expected_d, abs=1e-9)


def test_stochrsi_latest_values_emits_strategy_keys(frame: pd.DataFrame) -> None:
    """``latest_values`` emits exactly the flat keys StochRSITrendEntry reads.

    The consumer requires ``stochrsi_k``, ``stochrsi_d``, ``stochrsi_k_prev``;
    ``stochrsi_k_prev`` must be the *previous* bar's %K for crossover detection.
    """
    calc = StochRSICalculator()
    out = calc.calculate(frame.copy())
    values = calc.latest_values(frame.copy())

    assert set(values) == {"stochrsi_k", "stochrsi_d", "stochrsi_k_prev"}
    assert values["stochrsi_k"] == pytest.approx(_STOCHRSI_K, abs=_TOL)
    assert values["stochrsi_d"] == pytest.approx(_STOCHRSI_D, abs=_TOL)
    assert values["stochrsi_k_prev"] == pytest.approx(_STOCHRSI_K_PREV, abs=_TOL)
    # k_prev is genuinely the prior bar's %K, not the current one.
    assert values["stochrsi_k_prev"] == pytest.approx(
        float(out["stochrsi_k"].iloc[-2]), abs=1e-9
    )


def test_stochrsi_latest_values_neutral_when_insufficient() -> None:
    """With too little data, ``latest_values`` falls back to the neutral 50.

    This preserves the strategy's current default behavior (``data.get(k, 50)``)
    during warmup, so wiring the producer in is behavior-preserving until enough
    bars exist.
    """
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
