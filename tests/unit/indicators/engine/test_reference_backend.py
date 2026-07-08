"""ReferenceBackend: engine exposure of the reference calculators (P1-a).

Two guarantees:

* **Equivalence** — the backend is a zero-math adapter: every output series is
  bit-identical (``np.array_equal`` with ``equal_nan``) to calling the
  calculator classes directly, so the engine path can never drift from the
  ``shared.indicators.reference`` shim consumers.
* **Shadow comparability** — the reference convention plugs into the same
  :class:`ShadowDelta` mechanism as the other compat backends, pinning its
  measured relationship to :class:`TALibBackend`: RSI/ADX near-parity,
  ``atr_wilder`` == TA-Lib ATR exactly, ``atr`` (SMA mode) divergent
  (the documented delegation gate), MFI bit-level parity on trending data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared.indicators.engine import (
    IndicatorComputationError,
    IndicatorSpec,
    OHLCVWindow,
    ReferenceBackend,
    ShadowDelta,
    UnsupportedIndicatorError,
    reference_indicator_engine,
)
from shared.indicators.reference import (
    ADXCalculator,
    ATRCalculator,
    MFICalculator,
    StochRSICalculator,
    wilder_rsi,
)

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def arrays() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(7)
    n = 120
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.8, n))
    high = close + rng.uniform(0.05, 1.0, n)
    low = close - rng.uniform(0.05, 1.0, n)
    open_ = close + rng.normal(0.0, 0.3, n)
    volume = rng.uniform(1_000.0, 5_000.0, n)
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


@pytest.fixture(scope="module")
def window(arrays: dict[str, np.ndarray]) -> OHLCVWindow:
    return OHLCVWindow.from_sequences(**arrays)


@pytest.fixture(scope="module")
def backend() -> ReferenceBackend:
    return ReferenceBackend()


def _series(
    backend: ReferenceBackend,
    window: OHLCVWindow,
    indicator_id: str,
    params: dict | None = None,
) -> dict[str, np.ndarray]:
    spec = IndicatorSpec.create(indicator_id, params or {})
    return dict(backend.compute(spec, window).series)


# ---------------------------------------------------------------------------
# Equivalence: backend output == direct calculator output, bit for bit
# ---------------------------------------------------------------------------


def test_rsi_series_bit_identical(
    backend: ReferenceBackend, window: OHLCVWindow, arrays: dict[str, np.ndarray]
) -> None:
    out = _series(backend, window, "rsi", {"period": 14})["value"]
    direct = wilder_rsi(arrays["close"], period=14).to_numpy(dtype=float)
    assert np.array_equal(out, direct, equal_nan=True)


def test_adx_series_bit_identical(
    backend: ReferenceBackend, window: OHLCVWindow, arrays: dict[str, np.ndarray]
) -> None:
    out = _series(backend, window, "adx", {"period": 14})
    df = ADXCalculator(period=14).calculate(
        pd.DataFrame(
            {"high": arrays["high"], "low": arrays["low"], "close": arrays["close"]}
        )
    )
    for output, column in (
        ("value", "adx"),
        ("plus_di", "plus_di"),
        ("minus_di", "minus_di"),
        ("dx", "dx"),
    ):
        assert np.array_equal(
            out[output], df[column].to_numpy(dtype=float), equal_nan=True
        ), output


def test_stochrsi_series_bit_identical(
    backend: ReferenceBackend, window: OHLCVWindow, arrays: dict[str, np.ndarray]
) -> None:
    out = _series(
        backend,
        window,
        "stochrsi",
        {"rsi_period": 14, "stoch_period": 14, "k_period": 3, "d_period": 3},
    )
    df = StochRSICalculator().calculate(pd.DataFrame({"close": arrays["close"]}))
    for output, column in (
        ("value", "stochrsi"),
        ("k", "stochrsi_k"),
        ("d", "stochrsi_d"),
    ):
        assert np.array_equal(
            out[output], df[column].to_numpy(dtype=float), equal_nan=True
        ), output


@pytest.mark.parametrize(
    ("indicator_id", "mode"), [("atr", "sma"), ("atr_wilder", "wilder")]
)
def test_atr_series_bit_identical(
    backend: ReferenceBackend,
    window: OHLCVWindow,
    arrays: dict[str, np.ndarray],
    indicator_id: str,
    mode: str,
) -> None:
    out = _series(backend, window, indicator_id, {"period": 14})["value"]
    direct = ATRCalculator(period=14, mode=mode).atr_series(
        arrays["high"], arrays["low"], arrays["close"]
    )
    assert np.array_equal(out, direct, equal_nan=True)


def test_mfi_series_bit_identical_and_last_matches_scalar(
    backend: ReferenceBackend, window: OHLCVWindow, arrays: dict[str, np.ndarray]
) -> None:
    out = _series(backend, window, "mfi", {"period": 14})["value"]
    calc = MFICalculator(period=14)
    direct = calc.mfi_series(
        arrays["high"], arrays["low"], arrays["close"], arrays["volume"]
    )
    assert np.array_equal(out, direct, equal_nan=True)
    # The series' last bar is the exact scalar every regime consumer reads.
    scalar = calc.mfi_last(
        arrays["high"], arrays["low"], arrays["close"], arrays["volume"]
    )
    assert float(out[-1]) == scalar


def test_mfi_series_warmup_is_nan(arrays: dict[str, np.ndarray]) -> None:
    """Series form keeps NaN warmup (scalar form maps it to the 50.0 sentinel)."""
    series = MFICalculator(period=14).mfi_series(
        arrays["high"], arrays["low"], arrays["close"], arrays["volume"]
    )
    assert np.isnan(series[:14]).all()
    assert np.isfinite(series[14:]).all()


def test_mfi_series_prefix_matches_scalar_on_prefix(
    arrays: dict[str, np.ndarray],
) -> None:
    """Value at bar i == mfi_last on the window ending at bar i (causality)."""
    calc = MFICalculator(period=14)
    series = calc.mfi_series(
        arrays["high"], arrays["low"], arrays["close"], arrays["volume"]
    )
    for i in (14, 40, 77):
        prefix = calc.mfi_last(
            arrays["high"][: i + 1],
            arrays["low"][: i + 1],
            arrays["close"][: i + 1],
            arrays["volume"][: i + 1],
        )
        assert float(series[i]) == prefix, f"bar {i}"


# ---------------------------------------------------------------------------
# Engine plumbing: ids, flat keys, errors, registry singleton
# ---------------------------------------------------------------------------


def test_supported_ids(backend: ReferenceBackend) -> None:
    assert backend.supported_ids() == frozenset(
        {"rsi", "adx", "stochrsi", "atr", "atr_wilder", "mfi"}
    )


def test_flat_latest_keys(backend: ReferenceBackend, window: OHLCVWindow) -> None:
    stochrsi_flat = backend.compute(
        IndicatorSpec.create("stochrsi", {}), window
    ).flat_latest()
    assert set(stochrsi_flat) == {"stochrsi", "stochrsi_k", "stochrsi_d"}
    adx_flat = backend.compute(
        IndicatorSpec.create("adx", {"period": 14}), window
    ).flat_latest()
    assert set(adx_flat) == {"adx", "adx_plus_di", "adx_minus_di", "adx_dx"}


def test_unsupported_id_raises(backend: ReferenceBackend, window: OHLCVWindow) -> None:
    with pytest.raises(UnsupportedIndicatorError):
        backend.compute(IndicatorSpec.create("bollinger", {}), window)


def test_empty_window_raises(backend: ReferenceBackend) -> None:
    empty = OHLCVWindow.from_sequences(open=[], high=[], low=[], close=[], volume=[])
    with pytest.raises(IndicatorComputationError):
        backend.compute(IndicatorSpec.create("rsi", {}), empty)


def test_reference_indicator_engine_is_cached_singleton() -> None:
    engine = reference_indicator_engine()
    assert engine is reference_indicator_engine()
    assert engine.supported_ids() == frozenset(
        {"rsi", "adx", "stochrsi", "atr", "atr_wilder", "mfi"}
    )
    assert isinstance(engine.backends[0], ReferenceBackend)


# ---------------------------------------------------------------------------
# Shadow comparability vs TALibBackend (same mechanism as the compat backends)
# ---------------------------------------------------------------------------


def _talib_latest(window: OHLCVWindow, indicator_id: str, params: dict) -> float:
    from shared.indicators.engine.talib_backend import TALibBackend

    result = TALibBackend().compute(IndicatorSpec.create(indicator_id, params), window)
    return float(result.latest["value"])


def _reference_latest(
    backend: ReferenceBackend, window: OHLCVWindow, indicator_id: str, params: dict
) -> float:
    result = backend.compute(IndicatorSpec.create(indicator_id, params), window)
    return float(result.latest["value"])


def test_shadow_rsi_and_adx_near_parity_with_talib(
    backend: ReferenceBackend, window: OHLCVWindow
) -> None:
    pytest.importorskip("talib")
    for indicator_id in ("rsi", "adx"):
        delta = ShadowDelta(
            indicator=indicator_id,
            engine_value=_talib_latest(window, indicator_id, {"period": 14}),
            legacy_value=_reference_latest(
                backend, window, indicator_id, {"period": 14}
            ),
        )
        # Same Wilder family; residual gap is the warmup-seed difference only.
        assert delta.within(abs_tol=0.01), (indicator_id, delta.abs_delta)


def test_shadow_atr_wilder_is_talib_exact(
    backend: ReferenceBackend, window: OHLCVWindow
) -> None:
    pytest.importorskip("talib")
    delta = ShadowDelta(
        indicator="atr_wilder",
        engine_value=_talib_latest(window, "atr", {"period": 14}),
        legacy_value=_reference_latest(backend, window, "atr_wilder", {"period": 14}),
    )
    assert delta.within(abs_tol=1e-9), delta.abs_delta


def test_shadow_atr_sma_diverges_from_talib(
    backend: ReferenceBackend, window: OHLCVWindow
) -> None:
    """SMA-of-TR vs Wilder ATR genuinely differ — the documented delegation gate."""
    pytest.importorskip("talib")
    delta = ShadowDelta(
        indicator="atr",
        engine_value=_talib_latest(window, "atr", {"period": 14}),
        legacy_value=_reference_latest(backend, window, "atr", {"period": 14}),
    )
    assert not delta.within(abs_tol=1e-3, rel_tol=1e-3), delta.abs_delta


def test_shadow_mfi_bit_level_parity_with_talib(
    backend: ReferenceBackend, window: OHLCVWindow
) -> None:
    pytest.importorskip("talib")
    delta = ShadowDelta(
        indicator="mfi",
        engine_value=_talib_latest(window, "mfi", {"period": 14}),
        legacy_value=_reference_latest(backend, window, "mfi", {"period": 14}),
    )
    # Identical classification + ratio math on non-flat data (sentinels differ).
    assert delta.within(abs_tol=1e-9), delta.abs_delta
