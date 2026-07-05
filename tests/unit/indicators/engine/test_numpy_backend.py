"""Unit tests for the NumPy backend + multi-backend routing.

Pure NumPy — runs without TA-Lib. Expected values are hand-computed.
"""

from __future__ import annotations

import pytest

from shared.indicators.engine.numpy_backend import NumpyBackend
from shared.indicators.engine.registry import default_engine
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow


@pytest.fixture
def backend() -> NumpyBackend:
    return NumpyBackend()


def test_supported_ids(backend: NumpyBackend) -> None:
    assert backend.supported_ids() == {"vwap", "rvol"}


def test_vwap_cumulative(backend: NumpyBackend) -> None:
    # tp == close (high==low==close); volume all 1 ->
    # vwap = cumsum(close)/count = [10, 15, 20].
    window = OHLCVWindow.from_sequences(
        open=[10, 20, 30],
        high=[10, 20, 30],
        low=[10, 20, 30],
        close=[10, 20, 30],
        volume=[1, 1, 1],
    )
    flat = backend.compute(IndicatorSpec.create("vwap"), window).flat_latest()
    assert flat["vwap"] == pytest.approx(20.0)


def test_vwap_handles_zero_leading_volume(backend: NumpyBackend) -> None:
    window = OHLCVWindow.from_sequences(
        open=[10, 20],
        high=[10, 20],
        low=[10, 20],
        close=[10, 20],
        volume=[0, 2],
    )
    # first bar cum_v==0 -> NaN (dropped); second: (10*0 + 20*2)/2 = 20.
    flat = backend.compute(IndicatorSpec.create("vwap"), window).flat_latest()
    assert flat["vwap"] == pytest.approx(20.0)


def test_rvol_ratio(backend: NumpyBackend) -> None:
    # volume = [1,1,1,1,2], short=2, long=4.
    # last short mean = (1+2)/2 = 1.5; last long mean = (1+1+1+2)/4 = 1.25.
    # rvol = 1.5 / 1.25 = 1.2.
    window = OHLCVWindow.from_sequences(
        open=[1, 1, 1, 1, 2],
        high=[1, 1, 1, 1, 2],
        low=[1, 1, 1, 1, 2],
        close=[1, 1, 1, 1, 2],
        volume=[1, 1, 1, 1, 2],
    )
    spec = IndicatorSpec.create("rvol", {"short_window": 2, "long_window": 4})
    flat = backend.compute(spec, window).flat_latest()
    assert flat["rvol"] == pytest.approx(1.2)


def test_rvol_short_window_yields_no_value(backend: NumpyBackend) -> None:
    window = OHLCVWindow.from_sequences(
        open=[1, 1], high=[1, 1], low=[1, 1], close=[1, 1], volume=[1, 1]
    )
    spec = IndicatorSpec.create("rvol", {"short_window": 2, "long_window": 20})
    # long window never fills -> all NaN -> dropped.
    assert backend.compute(spec, window).flat_latest() == {}


def test_default_engine_routes_across_backends() -> None:
    engine = default_engine()
    # NumPy backend always registers -> vwap/rvol resolvable.
    assert engine.resolve("vwap").name == "numpy"
    assert "vwap" in engine.supported_ids()
    assert "rvol" in engine.supported_ids()


def test_default_engine_prefers_talib_for_standard_ids() -> None:
    pytest.importorskip("talib")
    engine = default_engine()
    # TA-Lib registered first -> wins for ids it covers.
    assert engine.resolve("rsi").name == "talib"
    assert engine.resolve("atr").name == "talib"
