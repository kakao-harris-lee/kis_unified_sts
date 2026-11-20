"""Golden pin: DailyCompatBackend / calculate_daily_indicators bit-parity."""

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
    assert set(got) == set(exp)
    for key, value in exp.items():
        assert got[key] == pytest.approx(value, abs=1e-12, nan_ok=True)
