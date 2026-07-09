"""Golden numeric pins for the builder Indicator Context (P2-b safety net).

Pins the exact values ``build_indicator_context`` produces for a fixed
deterministic window so any refactor of the builder evaluation path (panel
caching, engine wiring) is provably value-invisible. If one of these numbers
moves, the change is NOT a refactor.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

pytest.importorskip("talib")

from shared.indicators.engine import OHLCVWindow  # noqa: E402
from shared.strategy_builder.indicator_context import (  # noqa: E402
    build_indicator_context,
)
from shared.strategy_builder.schema import BuilderState  # noqa: E402

# Last-bar values computed on main @ 6a1d272d (pre-caching). Bit-exact pins:
# the caching refactor must return the identical floats, not merely close ones.
_GOLDEN_LAST_BAR: dict[str, float] = {
    "b.lower": 101.63805954998742,
    "b.middle": 112.7663479280587,
    "b.upper": 123.89463630613,
    "e.value": 108.97033124769105,
    "m.histogram": -0.5202011893041785,
    "m.signal": -0.6280422707300588,
    "m.value": -1.1482434600342373,
    "r.value": 51.35917226541754,
    "v.value": 109.04569526771837,
}


def _golden_window() -> OHLCVWindow:
    n = 60
    close = np.array([100.0 + 10.0 * math.sin(i / 5.0) + 0.3 * i for i in range(n)])
    return OHLCVWindow.from_sequences(
        open=close - 0.5,
        high=close + 1.5,
        low=close - 1.5,
        close=close,
        volume=np.array([1000.0 + 37.0 * (i % 7) for i in range(n)]),
    )


def _golden_state() -> BuilderState:
    return BuilderState.model_validate(
        {
            "metadata": {"name": "golden"},
            "asset_class": "stock",
            "indicators": [
                {"indicator_id": "rsi", "alias": "r", "params": {"period": 14}},
                {"indicator_id": "ema", "alias": "e", "params": {"period": 5}},
                {
                    "indicator_id": "bollinger",
                    "alias": "b",
                    "params": {"period": 20, "std": 2},
                },
                {
                    "indicator_id": "macd",
                    "alias": "m",
                    "params": {"fast": 12, "slow": 26, "signal": 9},
                },
                {"indicator_id": "vwap", "alias": "v", "params": {}},
            ],
            "entry": {"conditions": []},
            "exit": {"conditions": []},
        }
    )


def test_indicator_context_last_bar_values_are_pinned() -> None:
    ctx = build_indicator_context(_golden_state(), _golden_window())
    for column, expected in _GOLDEN_LAST_BAR.items():
        actual = float(ctx.frame[column].iloc[-1])
        assert actual == expected, f"{column}: {actual!r} != pinned {expected!r}"


def test_indicator_context_column_set_is_pinned() -> None:
    ctx = build_indicator_context(_golden_state(), _golden_window())
    assert set(ctx.frame.columns) == {
        "open",
        "high",
        "low",
        "close",
        "volume",
        *_GOLDEN_LAST_BAR,
    }


def test_indicator_context_is_deterministic_across_calls() -> None:
    """Two evaluations of the same window must be value-identical.

    This is the invariant the panel cache relies on: repeated computation of
    one (spec, window) pair is pure, so memoizing it is behaviorally invisible.
    """
    state = _golden_state()
    window = _golden_window()
    first = build_indicator_context(state, window).frame
    second = build_indicator_context(state, window).frame
    assert list(first.columns) == list(second.columns)
    for column in first.columns:
        np.testing.assert_array_equal(
            first[column].to_numpy(), second[column].to_numpy()
        )
