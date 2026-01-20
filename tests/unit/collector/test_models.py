"""Test data collector models."""
import pytest
from datetime import datetime


def test_tick_data_creation():
    """Test TickData with L5 orderbook."""
    from shared.collector.models import TickData

    tick = TickData(
        symbol="101S06",
        timestamp=1705300800.123,
        bid_price_1=330.50,
        bid_qty_1=100,
        ask_price_1=330.55,
        ask_qty_1=150,
    )

    assert tick.symbol == "101S06"
    assert tick.bid_price_1 == 330.50
    assert tick.ask_price_1 == 330.55


def test_tick_data_to_dict():
    """Test TickData serialization excludes None values."""
    from shared.collector.models import TickData

    tick = TickData(
        symbol="101S06",
        timestamp=1705300800.0,
        bid_price_1=330.50,
        bid_qty_1=100,
        ask_price_1=330.55,
        ask_qty_1=150,
        current_price=330.52,
    )

    data = tick.to_dict()

    assert "bid_price_2" not in data  # None values excluded
    assert data["current_price"] == 330.52


def test_tick_data_spread():
    """Test spread calculation."""
    from shared.collector.models import TickData

    tick = TickData(
        symbol="101S06",
        timestamp=1705300800.0,
        bid_price_1=330.50,
        bid_qty_1=100,
        ask_price_1=330.55,
        ask_qty_1=150,
    )

    assert tick.spread == pytest.approx(0.05)
    assert tick.mid_price == pytest.approx(330.525)
