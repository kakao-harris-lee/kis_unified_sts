"""Contract pins for ``shared.indicators.reference`` (P1-a absorption gate).

These tests freeze the exact numeric contracts of the reference calculators
BEFORE the math moves behind the engine (``ReferenceBackend``) so the move is
provably value-preserving. They import only the public
``shared.indicators.reference`` surface, so they must pass identically before
and after the restructure (the module becomes a thin re-export shim).

Pinned contracts:

* **Warmup**: NaN-preserving warmup positions (first valid index) for the
  Wilder RSI, ATR (both modes), ADX, and StochRSI %K series.
* **Flat-window sentinels** (verified empirically, not from lore):
    - reference Wilder RSI on a flat window -> ``50.0`` (TA-Lib -> ``0.0``);
    - reference MFI on a flat window -> ``100.0`` (zero negative flow — the
      regime convention; TA-Lib -> ``0.0``);
    - reference MFI with fewer than ``period`` classified bars -> ``50.0``;
    - reference StochRSI on a flat RSI window -> ``50.0``.
* **ATR smoothing modes**: exact last-bar values for ``mode="sma"`` vs
  ``mode="wilder"`` on the fixed synthetic series (they genuinely differ).
* **StochRSI %K/%D**: exact last-bar (and prior-bar %K) values on the fixed
  synthetic series.
* **ADX / MFI**: exact last-bar values on the fixed synthetic series.

Input generation is the same RNG-free closed-form OHLCV as
``test_reference.py`` so the snapshot constants are deterministic.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from shared.indicators.reference import (
    ADXCalculator,
    ATRCalculator,
    MFICalculator,
    StochRSICalculator,
    wilder_rsi,
)

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


# Exact last-bar snapshots on the deterministic series (period=14 defaults).
_RSI_LAST = 47.09914310988074
_ATR_SMA_LAST = 2.3615510655506173
_ATR_WILDER_LAST = 2.2903558861698596
_STOCHRSI_K_LAST = 11.901304088609335
_STOCHRSI_D_LAST = 35.74870786347318
_STOCHRSI_K_PREV = 33.2860793169478
_ADX_LAST = 31.634447762095665
_MFI_LAST = 55.974243199902375

_EXACT = 1e-9


# ---------------------------------------------------------------------------
# Warmup contracts (NaN-preserving; first valid index)
# ---------------------------------------------------------------------------


def test_warmup_rsi_first_valid_at_period(frame: pd.DataFrame) -> None:
    """Wilder RSI warms up at index ``period`` (NaN before, no neutral fill)."""
    rsi = wilder_rsi(frame["close"], period=14)
    assert rsi.iloc[:14].isna().all()
    assert int(rsi.first_valid_index()) == 14


def test_warmup_atr_first_valid_at_period(ohlcv: dict[str, list[float]]) -> None:
    """Both ATR modes warm up at index ``period`` (bar 0 has no True Range)."""
    for mode in ("sma", "wilder"):
        series = ATRCalculator(period=14, mode=mode).atr_series(
            ohlcv["high"], ohlcv["low"], ohlcv["close"]
        )
        finite = np.flatnonzero(np.isfinite(series))
        assert finite.size > 0
        assert int(finite[0]) == 14, f"mode={mode}"


def test_warmup_adx_first_valid_index(frame: pd.DataFrame) -> None:
    """ADX needs two Wilder passes: first valid at ``2 * period - 1`` (index 27)."""
    out = ADXCalculator(period=14).calculate(frame)
    assert int(out["adx"].first_valid_index()) == 27


def test_warmup_stochrsi_k_first_valid_index(frame: pd.DataFrame) -> None:
    """%K needs RSI warmup + stoch window: first valid at index 27."""
    out = StochRSICalculator().calculate(frame)
    assert int(out["stochrsi_k"].first_valid_index()) == 27


# ---------------------------------------------------------------------------
# Flat-window sentinels (reference vs TA-Lib divergence pinned explicitly)
# ---------------------------------------------------------------------------


def test_flat_window_rsi_sentinel_is_50() -> None:
    """Reference Wilder RSI returns neutral 50.0 on a flat window."""
    flat = pd.Series([100.0] * 40)
    rsi = wilder_rsi(flat, period=14)
    assert float(rsi.iloc[-1]) == pytest.approx(50.0, abs=_EXACT)


def test_flat_window_mfi_sentinel_is_100() -> None:
    """Reference MFI returns 100.0 on a flat window (zero negative flow).

    This is the regime detector's own contract — NOT the 50.0 the intraday
    streaming MFI uses on flat windows. Pinned so the absorption cannot
    silently "fix" it to either 50 or TA-Lib's 0.
    """
    flat = [100.0] * 40
    vol = [1000.0] * 40
    assert MFICalculator(period=14).mfi_last(flat, flat, flat, vol) == pytest.approx(
        100.0, abs=_EXACT
    )


def test_insufficient_data_mfi_sentinel_is_50() -> None:
    """Reference MFI returns neutral 50.0 with fewer than ``period`` flows."""
    mfi = MFICalculator(period=14).mfi_last(
        [100.0, 101.0], [99.0, 100.0], [99.5, 100.5], [1000.0, 1000.0]
    )
    assert mfi == pytest.approx(50.0, abs=_EXACT)


def test_flat_window_stochrsi_sentinel_is_50() -> None:
    """Reference StochRSI normalizes a flat RSI window to neutral 50.0."""
    flat = pd.DataFrame({"close": [100.0] * 40})
    out = StochRSICalculator().calculate(flat)
    raw = out["stochrsi"].dropna()
    assert not raw.empty
    assert np.allclose(raw.to_numpy(), 50.0, atol=_EXACT)


def test_flat_window_sentinels_diverge_from_talib() -> None:
    """TA-Lib returns 0.0 where the reference convention returns 50/100.

    Empirically verified divergence (RSI 50 vs 0, MFI 100 vs 0). This is the
    convention gap the ``STS_INDICATOR_CONVENTION`` gate exists for; the P1-a
    absorption must preserve the reference side untouched.
    """
    talib = pytest.importorskip("talib")
    flat = np.full(40, 100.0)
    vol = np.full(40, 1000.0)
    assert float(talib.RSI(flat, timeperiod=14)[-1]) == pytest.approx(0.0, abs=_EXACT)
    assert float(talib.MFI(flat, flat, flat, vol, timeperiod=14)[-1]) == pytest.approx(
        0.0, abs=_EXACT
    )


# ---------------------------------------------------------------------------
# ATR mode="sma" vs mode="wilder" exact outputs
# ---------------------------------------------------------------------------


def test_atr_sma_mode_exact_snapshot(ohlcv: dict[str, list[float]]) -> None:
    atr = ATRCalculator(period=14, mode="sma").atr_last(
        ohlcv["high"], ohlcv["low"], ohlcv["close"]
    )
    assert atr == pytest.approx(_ATR_SMA_LAST, abs=_EXACT)


def test_atr_wilder_mode_exact_snapshot(ohlcv: dict[str, list[float]]) -> None:
    atr = ATRCalculator(period=14, mode="wilder").atr_last(
        ohlcv["high"], ohlcv["low"], ohlcv["close"]
    )
    assert atr == pytest.approx(_ATR_WILDER_LAST, abs=_EXACT)


def test_atr_modes_differ_on_real_shaped_data(ohlcv: dict[str, list[float]]) -> None:
    """The two smoothing modes are genuinely distinct conventions."""
    assert abs(_ATR_SMA_LAST - _ATR_WILDER_LAST) > 1e-3


# ---------------------------------------------------------------------------
# StochRSI %K / %D exact outputs on the fixed synthetic series
# ---------------------------------------------------------------------------


def test_stochrsi_k_d_exact_snapshot(frame: pd.DataFrame) -> None:
    calc = StochRSICalculator()
    out = calc.calculate(frame.copy())
    assert float(out["stochrsi_k"].iloc[-1]) == pytest.approx(
        _STOCHRSI_K_LAST, abs=_EXACT
    )
    assert float(out["stochrsi_d"].iloc[-1]) == pytest.approx(
        _STOCHRSI_D_LAST, abs=_EXACT
    )
    values = calc.latest_values(frame.copy())
    assert values["stochrsi_k"] == pytest.approx(_STOCHRSI_K_LAST, abs=_EXACT)
    assert values["stochrsi_d"] == pytest.approx(_STOCHRSI_D_LAST, abs=_EXACT)
    assert values["stochrsi_k_prev"] == pytest.approx(_STOCHRSI_K_PREV, abs=_EXACT)


# ---------------------------------------------------------------------------
# RSI / ADX / MFI exact last-bar values
# ---------------------------------------------------------------------------


def test_rsi_exact_snapshot(frame: pd.DataFrame) -> None:
    rsi = wilder_rsi(frame["close"], period=14)
    assert float(rsi.iloc[-1]) == pytest.approx(_RSI_LAST, abs=_EXACT)


def test_adx_exact_snapshot(frame: pd.DataFrame) -> None:
    out = ADXCalculator(period=14).calculate(frame)
    assert float(out["adx"].dropna().iloc[-1]) == pytest.approx(_ADX_LAST, abs=_EXACT)


def test_mfi_exact_snapshot(ohlcv: dict[str, list[float]]) -> None:
    mfi = MFICalculator(period=14).mfi_last(
        ohlcv["high"], ohlcv["low"], ohlcv["close"], ohlcv["volume"]
    )
    assert mfi == pytest.approx(_MFI_LAST, abs=_EXACT)
