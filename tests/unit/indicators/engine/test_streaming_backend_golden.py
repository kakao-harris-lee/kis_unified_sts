"""Golden pin: StreamingCompatBackend == the pre-retirement _calc_* values.

``streaming_compat_golden.json`` was captured from
``services.trading.indicator_calculations.IndicatorCalculationMixin._calc_*``
BEFORE the math was relocated into the engine. These tests assert the backend (and
therefore the delegated runtime ``_calc_*``) reproduce those values bit-for-bit
across short/long/flat/insufficient windows — the guarantee that the value-
preserving retirement changed no live signal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.indicators.engine import (
    IndicatorSpec,
    OHLCVWindow,
    streaming_indicator_engine,
)

_GOLDEN = json.loads(
    (Path(__file__).parent / "streaming_compat_golden.json").read_text()
)


def _window(ohlcv: list[list[float]]) -> OHLCVWindow:
    return OHLCVWindow.from_sequences(
        open=[r[0] for r in ohlcv],
        high=[r[1] for r in ohlcv],
        low=[r[2] for r in ohlcv],
        close=[r[3] for r in ohlcv],
        volume=[r[4] for r in ohlcv],
    )


@pytest.mark.parametrize("case", _GOLDEN, ids=lambda c: c["name"])
def test_streaming_backend_matches_golden(case) -> None:
    eng = streaming_indicator_engine()
    w = _window(case["ohlcv"])

    def flat(iid: str, params: dict) -> dict:
        return eng.compute(IndicatorSpec.create(iid, params), w).flat_latest()

    # RSI — always present (50.0 sentinel on insufficient/flat)
    rsi = flat("rsi", {"period": 14}).get("rsi")
    assert rsi == pytest.approx(case["rsi"], abs=1e-12)

    # Bollinger — legacy computes a (partial) band for any len>=2, incl. len<period
    bb = flat("bollinger", {"period": 20, "std": 2.0})
    lo, mid, up = case["bb"]
    assert bb["bb_lower"] == pytest.approx(lo, abs=1e-12)
    assert bb["bb_middle"] == pytest.approx(mid, abs=1e-12)
    assert bb["bb_upper"] == pytest.approx(up, abs=1e-12)

    # MFI / ADX — None (insufficient) => key omitted
    mfi = flat("mfi", {"period": 14}).get("mfi")
    if case["mfi"] is None:
        assert mfi is None
    else:
        assert mfi == pytest.approx(case["mfi"], abs=1e-12)

    adx = flat("adx", {"period": 14}).get("adx")
    if case["adx"] is None:
        assert adx is None
    else:
        assert adx == pytest.approx(case["adx"], abs=1e-12)

    # RVOL — always present (1.0 fallback)
    rvol = flat("rvol", {"short_window": 5, "long_window": 20}).get("rvol")
    assert rvol == pytest.approx(case["rvol"], abs=1e-12)

    # Stochastic fast %K / %D
    st = flat("stochastic", {"k_period": 14, "d_period": 3})
    k, d = case["stoch"]
    assert st["stoch_k"] == pytest.approx(k, abs=1e-12)
    assert st["stoch_d"] == pytest.approx(d, abs=1e-12)
