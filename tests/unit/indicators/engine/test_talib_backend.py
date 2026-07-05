"""Unit tests for the TA-Lib backend.

Skipped entirely when the TA-Lib wheel is absent. The value these assert is the
normalization contract (catalog id/output -> canonical flat key) and parity with
a direct TA-Lib call, not TA-Lib's own math.
"""

from __future__ import annotations

import numpy as np
import pytest

talib = pytest.importorskip("talib")

from shared.indicators.engine.base import (  # noqa: E402
    IndicatorComputationError,
    UnsupportedIndicatorError,
)
from shared.indicators.engine.registry import default_engine  # noqa: E402
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow  # noqa: E402
from shared.indicators.engine.talib_backend import TALibBackend  # noqa: E402


@pytest.fixture(scope="module")
def window() -> OHLCVWindow:
    rng = np.random.default_rng(42)
    n = 200
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))
    high = close + rng.uniform(0.0, 1.0, n)
    low = close - rng.uniform(0.0, 1.0, n)
    open_ = close + rng.normal(0.0, 0.5, n)
    volume = rng.uniform(1_000.0, 5_000.0, n)
    return OHLCVWindow.from_sequences(
        open=open_, high=high, low=low, close=close, volume=volume
    )


@pytest.fixture(scope="module")
def backend() -> TALibBackend:
    return TALibBackend()


def test_available_is_true_here() -> None:
    assert TALibBackend.available() is True


def test_supported_ids_cover_standard_set(backend: TALibBackend) -> None:
    ids = backend.supported_ids()
    for expected in ("rsi", "atr", "adx", "bollinger", "macd", "stochastic"):
        assert expected in ids
    # TA-Lib does not provide these; they must NOT be claimed.
    for absent in ("vwap", "rvol", "volume_acceleration", "ichimoku"):
        assert absent not in ids


def test_rsi_parity_with_direct_talib(backend: TALibBackend, window) -> None:
    spec = IndicatorSpec.create("rsi", {"period": 14})
    got = backend.compute(spec, window).flat_latest()["rsi"]
    reference = talib.RSI(window.close, timeperiod=14)
    expected = float(reference[np.isfinite(reference)][-1])
    assert got == pytest.approx(expected, rel=1e-9)


def test_atr_parity_with_direct_talib(backend: TALibBackend, window) -> None:
    spec = IndicatorSpec.create("atr", {"period": 14})
    got = backend.compute(spec, window).flat_latest()["atr"]
    ref = talib.ATR(window.high, window.low, window.close, timeperiod=14)
    expected = float(ref[np.isfinite(ref)][-1])
    assert got == pytest.approx(expected, rel=1e-9)


def test_adx_parity_with_direct_talib(backend: TALibBackend, window) -> None:
    spec = IndicatorSpec.create("adx", {"period": 14})
    got = backend.compute(spec, window).flat_latest()["adx"]
    ref = talib.ADX(window.high, window.low, window.close, timeperiod=14)
    expected = float(ref[np.isfinite(ref)][-1])
    assert got == pytest.approx(expected, rel=1e-9)


def test_compute_latest_default_matches_flat_latest(
    backend: TALibBackend, window
) -> None:
    # Exercises the base compute_latest() default (batch -> finite tail).
    spec = IndicatorSpec.create("rsi", {"period": 14})
    assert (
        backend.compute_latest(spec, window)
        == backend.compute(spec, window).flat_latest()
    )


def test_bollinger_flat_keys_are_normalized(backend: TALibBackend, window) -> None:
    spec = IndicatorSpec.create("bollinger", {"period": 20, "std": 2})
    flat = backend.compute(spec, window).flat_latest()
    assert set(flat) == {"bb_upper", "bb_middle", "bb_lower"}
    assert flat["bb_upper"] > flat["bb_middle"] > flat["bb_lower"]


def test_macd_flat_keys_are_normalized(backend: TALibBackend, window) -> None:
    spec = IndicatorSpec.create("macd", {"fast": 12, "slow": 26, "signal": 9})
    flat = backend.compute(spec, window).flat_latest()
    assert set(flat) == {"macd", "macd_signal", "macd_hist"}


def test_stochastic_flat_keys_are_normalized(backend: TALibBackend, window) -> None:
    spec = IndicatorSpec.create("stochastic", {"k_period": 14, "d_period": 3})
    flat = backend.compute(spec, window).flat_latest()
    assert set(flat) == {"stoch_k", "stoch_d"}
    assert 0.0 <= flat["stoch_k"] <= 100.0


def test_ema_flat_key_embeds_period(backend: TALibBackend, window) -> None:
    spec = IndicatorSpec.create("ema", {"period": 20})
    flat = backend.compute(spec, window).flat_latest()
    assert set(flat) == {"ema_20"}


def test_trix_emits_value_and_signal(backend: TALibBackend, window) -> None:
    spec = IndicatorSpec.create("trix", {"n": 12, "signal": 9})
    flat = backend.compute(spec, window).flat_latest()
    assert "trix" in flat
    assert "trix_signal" in flat


def test_unsupported_indicator_raises(backend: TALibBackend, window) -> None:
    with pytest.raises(UnsupportedIndicatorError):
        backend.compute(IndicatorSpec.create("vwap"), window)


def test_empty_window_raises(backend: TALibBackend) -> None:
    empty = OHLCVWindow.from_sequences(open=[], high=[], low=[], close=[], volume=[])
    with pytest.raises(IndicatorComputationError, match="empty"):
        backend.compute(IndicatorSpec.create("rsi", {"period": 14}), empty)


def test_short_window_yields_no_finite_latest(backend: TALibBackend) -> None:
    # 5 bars, RSI(14) never warms up -> all-NaN -> flat_latest drops it.
    short = OHLCVWindow.from_sequences(
        open=[1, 2, 3, 4, 5],
        high=[1, 2, 3, 4, 5],
        low=[1, 2, 3, 4, 5],
        close=[1, 2, 3, 4, 5],
        volume=[1, 1, 1, 1, 1],
    )
    flat = backend.compute(
        IndicatorSpec.create("rsi", {"period": 14}), short
    ).flat_latest()
    assert flat == {}


def test_default_engine_uses_talib(window) -> None:
    engine = default_engine()
    panel = engine.flat_panel(
        [
            IndicatorSpec.create("rsi", {"period": 14}),
            IndicatorSpec.create("bollinger", {"period": 20, "std": 2}),
        ],
        window,
    )
    assert "rsi" in panel
    assert {"bb_upper", "bb_middle", "bb_lower"} <= set(panel)
