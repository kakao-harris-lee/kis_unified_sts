"""Shadow parity harness: new engine vs runtime ``_calc_*`` on identical candles.

This is a *characterization + gate* test (same spirit as
``tests/unit/indicators/test_calc_parity.py``): it pins the current relationship
between the TA-Lib engine and the legacy runtime calculators so a future
delegation makes the delta explicit. Measured on a fixed seed:

* **ADX**  — parity (Δ ~= 0.002, both Wilder) → **delegate-safe, no value change**.
* **ATR**  — divergent (legacy ``_calc_atr_raw`` is SMA-of-TR, TA-Lib is Wilder) →
  **backtest gate required** before delegation (affects stops/edge filters).
* **Stoch**— divergent (legacy returns fast %K, TA-Lib ``STOCH`` is slow) → **gate**
  (or switch the backend to ``STOCHF`` to preserve the fast convention).
* **Bollinger** — middle band parity (both 20-SMA); the upper/lower diverge because
  legacy ``_calc_bb`` uses sample std (ddof=1) and TA-Lib uses population std
  (ddof=0) → **gate** (band width changes on delegation).

If any of these relationships changes, this test fails loudly and whoever changed
it updates the expectation deliberately.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

talib = pytest.importorskip("talib")

from services.trading.indicator_calculations import (  # noqa: E402
    IndicatorCalculationMixin as Legacy,
)
from services.trading.indicator_candles import Candle  # noqa: E402
from shared.indicators.engine import (  # noqa: E402
    IndicatorSpec,
    default_engine,
)
from shared.indicators.engine.adapters import window_from_bars  # noqa: E402
from shared.indicators.engine.shadow import ShadowDelta  # noqa: E402


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
    # Both Wilder -> parity. Safe to delegate with no backtest gate.
    assert delta.within(abs_tol=0.1), f"ADX drifted from parity: {delta}"


def test_atr_diverges_and_needs_gate(candles: list[Candle]) -> None:
    new = _engine_latest(candles, "atr", {"period": 14})["atr"]
    old = Legacy._calc_atr_raw(candles, 14)
    delta = ShadowDelta("atr", new, old)
    # legacy SMA-of-TR vs TA-Lib Wilder: a real value change -> gate required.
    assert not delta.within(abs_tol=0.02), (
        "ATR unexpectedly matches legacy SMA; the SMA->Wilder gate may already "
        f"be resolved — update this expectation. {delta}"
    )
    assert new > 0.0 and old > 0.0


def test_stochastic_diverges_fast_vs_slow(candles: list[Candle]) -> None:
    new = _engine_latest(candles, "stochastic", {"k_period": 14, "d_period": 3})
    old_k, _old_d = Legacy._calc_stochastic(candles, period=14, smooth=3)
    delta = ShadowDelta("stoch_k", new["stoch_k"], old_k)
    # legacy fast %K vs TA-Lib slow %K: divergent by construction -> gate.
    assert not delta.within(
        abs_tol=2.0
    ), f"Stochastic unexpectedly matches; convention may have changed. {delta}"


def test_bollinger_middle_parity_but_bands_diverge(candles: list[Candle]) -> None:
    new = _engine_latest(candles, "bollinger", {"period": 20, "std": 2})
    # legacy _calc_bb only reads self.bb_period / self.bb_std -> duck-typed self.
    ns = SimpleNamespace(bb_period=20, bb_std=2.0)
    old_lower, old_mid, old_upper = Legacy._calc_bb(ns, [c.close for c in candles])
    # Middle band = 20-SMA in both -> parity, delegate-safe.
    assert ShadowDelta("bb_middle", new["bb_middle"], old_mid).within(abs_tol=1e-6)
    # Upper band: TA-Lib population std (ddof=0) vs legacy sample std (ddof=1);
    # legacy band is slightly wider -> gate required before delegating BB.
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
    # legacy ~0 -> rel_delta is inf, only abs_tol can pass
    z = ShadowDelta("y", 0.001, 0.0)
    assert z.rel_delta == float("inf")
    assert z.within(abs_tol=0.01)
