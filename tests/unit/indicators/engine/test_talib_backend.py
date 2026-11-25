"""Unit tests for the TA-Lib backend."""

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


def test_stochrsi_flat_keys_and_parity(backend: TALibBackend, window) -> None:
    spec = IndicatorSpec.create("stochrsi", {"period": 14, "k": 5, "d": 3})
    flat = backend.compute(spec, window).flat_latest()
    assert set(flat) == {"stochrsi_k", "stochrsi_d"}
    assert 0.0 <= flat["stochrsi_k"] <= 100.0
    fastk, _fastd = talib.STOCHRSI(
        window.close, timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0
    )
    expected = float(fastk[np.isfinite(fastk)][-1])
    assert flat["stochrsi_k"] == pytest.approx(expected, rel=1e-9)


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


@pytest.mark.parametrize("indicator_id", ["apo", "ppo"])
def test_apo_ppo_match_the_sma_variant_not_the_talib_default(
    backend: TALibBackend, window, indicator_id: str
) -> None:
    """Parity is asserted against matype=0 NAMED, never against the bare call."""
    func = getattr(talib, indicator_id.upper())
    got = backend.compute(
        IndicatorSpec.create(indicator_id, {"fast": 12, "slow": 26}), window
    ).flat_latest()[indicator_id]

    reference = func(window.close, fastperiod=12, slowperiod=26, matype=0)
    expected = float(reference[np.isfinite(reference)][-1])

    assert got == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("indicator_id", ["apo", "ppo"])
def test_apo_ppo_would_differ_under_the_other_matype(
    backend: TALibBackend, window, indicator_id: str
) -> None:
    """The concrete input that makes the pin above matter."""
    func = getattr(talib, indicator_id.upper())
    got = backend.compute(
        IndicatorSpec.create(indicator_id, {"fast": 12, "slow": 26}), window
    ).flat_latest()[indicator_id]

    ema_variant = func(window.close, fastperiod=12, slowperiod=26, matype=1)
    ema_latest = float(ema_variant[np.isfinite(ema_variant)][-1])

    assert got != pytest.approx(ema_latest, rel=1e-6)


def test_apo_ppo_pass_matype_explicitly_whatever_talib_defaults_to() -> None:
    """Catches the regression directly: the argument must be SENT, not inherited."""
    from shared.indicators.engine import talib_backend as tb

    seen: dict[str, dict[str, object]] = {}

    class _Spy:
        @staticmethod
        def APO(close, **kwargs):  # noqa: N802 - mirrors TA-Lib's name
            seen["apo"] = kwargs
            return np.zeros_like(close)

        @staticmethod
        def PPO(close, **kwargs):  # noqa: N802 - mirrors TA-Lib's name
            seen["ppo"] = kwargs
            return np.zeros_like(close)

    close = np.linspace(100.0, 120.0, 60)
    spy_window = OHLCVWindow.from_sequences(
        open=close, high=close, low=close, close=close, volume=np.ones_like(close)
    )

    tb._apo(_Spy, spy_window, {"fast": 12.0, "slow": 26.0})
    tb._ppo(_Spy, spy_window, {"fast": 12.0, "slow": 26.0})

    assert seen["apo"]["matype"] == 0
    assert seen["ppo"]["matype"] == 0
