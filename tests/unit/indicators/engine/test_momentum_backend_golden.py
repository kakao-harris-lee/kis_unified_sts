"""Golden pin: momentum.py delegation == pre-retirement values (full series)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from shared.indicators.momentum import calculate_all_momentum

_GOLDEN = json.loads(
    (Path(__file__).parent / "momentum_compat_golden.json").read_text()
)
_COLS = [
    "trix",
    "trix_signal",
    "cci",
    "macd_line",
    "macd_signal",
    "macd_oscillator",
    "sto_k",
    "sto_d",
    "williams_r",
    "obv",
    "rsi",
]


@pytest.mark.parametrize("case", _GOLDEN, ids=lambda c: c["name"])
def test_calculate_all_momentum_matches_golden(case) -> None:
    df = pd.DataFrame(case["ohlcv"], columns=["open", "high", "low", "close", "volume"])
    out = calculate_all_momentum(df.copy())
    for col in _COLS:
        got = out[col].to_numpy(dtype=float)
        exp = np.asarray(case["cols"][col], dtype=float)
        assert np.allclose(got, exp, rtol=0, atol=1e-9, equal_nan=True), col
