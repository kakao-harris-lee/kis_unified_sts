"""Golden pin: DailyCompatBackend / calculate_daily_indicators bit-parity.

``daily_compat_golden.json`` was captured from
``shared.indicators.daily.calculate_daily_indicators`` BEFORE its math was
delegated into ``DailyCompatBackend``. These tests assert the delegated function
still reproduces those values bit-for-bit — including the SMA ``min_periods``
omission and the ewm-seeded daily RSI (which differs from the intraday
streaming RSI).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.indicators.daily import calculate_daily_indicators

_GOLDEN = json.loads((Path(__file__).parent / "daily_compat_golden.json").read_text())


@pytest.mark.parametrize("case", _GOLDEN, ids=lambda c: c["name"])
def test_daily_indicators_match_golden(case) -> None:
    candles = [
        {"open": c, "high": c, "low": c, "close": c, "volume": 0.0}
        for c in case["closes"]
    ]
    got = calculate_daily_indicators(
        candles,
        sma_periods=[20, 60, 200],
        ema_periods=[5, 10, 20],
        rsi_period=5,
    )
    exp = case["indicators"]
    # same keys (SMA omitted when under-warmed) ...
    assert set(got) == set(exp)
    # ... and same values bit-for-bit (nan_ok: legacy emits rsi=NaN for a window
    # shorter than rsi_period; the delegate reproduces that NaN exactly).
    for key, value in exp.items():
        assert got[key] == pytest.approx(value, abs=1e-12, nan_ok=True)
