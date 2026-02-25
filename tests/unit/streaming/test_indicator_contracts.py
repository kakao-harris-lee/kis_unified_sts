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

    malformed = next(req for req in contract.requests if req.source_key == "momentum_xx")
    assert malformed.kind == IndicatorKind.BASE
    assert malformed.key == "momentum_xx"
