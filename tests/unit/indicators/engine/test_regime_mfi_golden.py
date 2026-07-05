"""Golden pin: regime MFI retirement is value-preserving.

``regime_mfi_golden.json`` captures ``AdaptiveRegimeDetector._calc_mfi`` BEFORE its
math was delegated to ``reference.MFICalculator``. Asserts both the reference
calculator and the (now-delegating) regime method reproduce those values bit-for-bit,
including the sentinels: 50.0 when fewer than ``period`` classified bars, and 100.0
on a flat window (negative flow == 0 — the regime detector's own contract, which
differs from the intraday streaming MFI's 50.0-on-flat).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from shared.indicators.reference import MFICalculator
from shared.regime.adaptive_detector import AdaptiveRegimeDetector

_GOLDEN = json.loads((Path(__file__).parent / "regime_mfi_golden.json").read_text())


@pytest.mark.parametrize("case", _GOLDEN, ids=lambda c: c["name"])
def test_regime_mfi_matches_golden(case) -> None:
    df = pd.DataFrame(case["ohlcv"], columns=["open", "high", "low", "close", "volume"])

    ref = MFICalculator(period=14).mfi_last(
        df["high"], df["low"], df["close"], df["volume"]
    )
    assert ref == pytest.approx(case["mfi"], abs=1e-12)

    # the delegating regime method reproduces it too (does not use `self`)
    regime = AdaptiveRegimeDetector._calc_mfi(object(), df, period=14)
    assert regime == pytest.approx(case["mfi"], abs=1e-12)
