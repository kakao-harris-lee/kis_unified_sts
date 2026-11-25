"""Shadow parity harness: new engine vs runtime ``_calc_*`` on identical candles."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

talib = pytest.importorskip("talib")

from shared.indicators.engine import (  # noqa: E402
    IndicatorSpec,
    default_engine,
)
from shared.indicators.engine.adapters import window_from_bars  # noqa: E402
from shared.indicators.engine.shadow import ShadowDelta  # noqa: E402
from shared.indicators.streaming.calculations import (  # noqa: E402
    IndicatorCalculationMixin as Legacy,
)
from shared.indicators.streaming.candles import Candle  # noqa: E402


@pytest.fixture(scope="module")
def candles() -> list[Candle]:
    rng = np.random.default_rng(7)
    n = 120
    close = 100.0 + np.cumsum(rng.normal(0.0, 0.8, n))
    high = close + rng.uniform(0.05, 1.0, n)
    low = close - rng.uniform(0.05, 1.0, n)
    open_ = close + rng.normal(0.0, 0.3, n)
    vol = rng.uniform(1_000.0, 5_000.0, n)
    return [
        Candle(
            open=float(open_[i]),
            high=float(high[i]),
            low=float(low[i]),
            close=float(close[i]),
            volume=float(vol[i]),
            minute=930 + i,
        )
        for i in range(n)
    ]


def _engine_latest(candles: list[Candle], indicator_id: str, params: dict) -> dict:
    window = window_from_bars(candles)
    spec = IndicatorSpec.create(indicator_id, params)
    return default_engine().compute(spec, window).flat_latest()


def test_window_from_bars_matches_candles(candles: list[Candle]) -> None:
    window = window_from_bars(candles)
    assert len(window) == len(candles)
    assert window.close[-1] == pytest.approx(candles[-1].close)
    assert window.high[0] == pytest.approx(candles[0].high)


def test_adx_is_delegate_safe(candles: list[Candle]) -> None:
    new = _engine_latest(candles, "adx", {"period": 14})["adx"]
    old = Legacy._calc_adx(candles, 14)
    assert old is not None
    delta = ShadowDelta("adx", new, float(old))
    assert delta.within(abs_tol=0.1), f"ADX drifted from parity: {delta}"


def test_atr_diverges_and_needs_gate(candles: list[Candle]) -> None:
    new = _engine_latest(candles, "atr", {"period": 14})["atr"]
    old = Legacy._calc_atr_raw(candles, 14)
    delta = ShadowDelta("atr", new, old)
    assert not delta.within(abs_tol=0.02), (
        "ATR unexpectedly matches legacy SMA; the SMA->Wilder gate may already "
        f"be resolved — update this expectation. {delta}"
    )
    assert new > 0.0 and old > 0.0


def test_stochastic_diverges_fast_vs_slow(candles: list[Candle]) -> None:
    new = _engine_latest(candles, "stochastic", {"k_period": 14, "d_period": 3})
    old_k, _old_d = Legacy._calc_stochastic(candles, period=14, smooth=3)
    delta = ShadowDelta("stoch_k", new["stoch_k"], old_k)
    assert not delta.within(
        abs_tol=2.0
    ), f"Stochastic unexpectedly matches; convention may have changed. {delta}"


def test_bollinger_middle_parity_but_bands_diverge(candles: list[Candle]) -> None:
    new = _engine_latest(candles, "bollinger", {"period": 20, "std": 2})
    ns = SimpleNamespace(bb_period=20, bb_std=2.0)
    old_lower, old_mid, old_upper = Legacy._calc_bb(ns, [c.close for c in candles])
    assert ShadowDelta("bb_middle", new["bb_middle"], old_mid).within(abs_tol=1e-6)
    upper = ShadowDelta("bb_upper", new["bb_upper"], old_upper)
    assert not upper.within(abs_tol=1e-4), f"BB ddof gate closed unexpectedly: {upper}"
    assert old_upper > new["bb_upper"]


def test_shadow_delta_semantics() -> None:
    d = ShadowDelta("x", 10.0, 9.0)
    assert d.abs_delta == pytest.approx(1.0)
    assert d.rel_delta == pytest.approx(1.0 / 9.0)
    assert d.within(abs_tol=1.0)
    assert d.within(rel_tol=0.2)
    assert not d.within(abs_tol=0.5, rel_tol=0.01)
    z = ShadowDelta("y", 0.001, 0.0)
    assert z.rel_delta == float("inf")
    assert z.within(abs_tol=0.01)
