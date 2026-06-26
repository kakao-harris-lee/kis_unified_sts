from __future__ import annotations

import pytest

from shared.indicators.contracts import (
    IndicatorContract,
    IndicatorKind,
    Timeframe,
)


def test_timeframe_parse_and_format():
    assert Timeframe.from_token("5m").minutes == 5
    assert Timeframe.from_token("1h").minutes == 60
    assert Timeframe.from_token("1d").minutes == 1440
    assert Timeframe(60).to_token() == "1h"
    assert Timeframe(1440).to_token() == "1d"
    assert Timeframe(15).to_token() == "15m"


def test_timeframe_parse_invalid_token_raises():
    with pytest.raises(ValueError):
        Timeframe.from_token("bad")


def test_indicator_contract_normalizes_required_keys():
    contract = IndicatorContract.from_required_keys(
        ["rsi", "momentum_5m", "momentum_1h", "ohlcv", "", "momentum_xx"]
    )

    assert contract.needs_ohlcv is True
    assert tuple(req.key for req in contract.momentum_requests) == (
        "momentum_5m",
        "momentum_1h",
    )

    malformed = next(
        req for req in contract.requests if req.source_key == "momentum_xx"
    )
    assert malformed.kind == IndicatorKind.BASE
    assert malformed.key == "momentum_xx"


def test_recent_range_minutes_derived_from_setup_c_keys():
    """Setup C's range keys encode the window in the key name (→ 15)."""
    contract = IndicatorContract.from_required_keys(
        ["atr", "last_15min_high", "last_15min_low"]
    )
    assert contract.recent_range_minutes == 15


def test_recent_range_minutes_none_without_range_keys():
    """Strategies that don't declare a range high/low yield no window."""
    contract = IndicatorContract.from_required_keys(["atr", "vwap", "prev_close"])
    assert contract.recent_range_minutes is None


def test_recent_range_minutes_picks_largest_declared_window():
    """Defensive: when several windows are declared, the largest is used."""
    contract = IndicatorContract.from_required_keys(
        ["last_15min_high", "last_30min_low"]
    )
    assert contract.recent_range_minutes == 30
