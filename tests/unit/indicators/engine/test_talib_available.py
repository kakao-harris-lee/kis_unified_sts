"""TA-Lib availability gate."""

from __future__ import annotations

import numpy as np


def test_talib_imports_and_computes() -> None:
    import talib

    closes = np.arange(1.0, 61.0)
    rsi = talib.RSI(closes, timeperiod=14)
    assert rsi.shape == closes.shape
    assert np.isfinite(rsi[-1])
    assert rsi[-1] > 90.0
