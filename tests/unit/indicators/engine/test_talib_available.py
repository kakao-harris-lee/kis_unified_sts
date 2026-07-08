"""TA-Lib availability gate.

The indicator engine's TA-Lib backend degrades gracefully when talib is
missing, which historically let shadow-parity comparisons silently skip on
hosts whose venv lacked the wheel. This test turns a missing TA-Lib install
into a loud suite failure in every environment that runs pytest (CI and the
deploy-host venv alike). Fix: ``pip install -e ".[dev]"``.
"""

from __future__ import annotations

import numpy as np


def test_talib_imports_and_computes() -> None:
    import talib

    closes = np.arange(1.0, 61.0)
    rsi = talib.RSI(closes, timeperiod=14)
    assert rsi.shape == closes.shape
    assert np.isfinite(rsi[-1])
    # Monotonically rising closes pin RSI near the top of its range.
    assert rsi[-1] > 90.0
