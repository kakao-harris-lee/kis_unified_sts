"""Test DataCollector class."""
import pytest
from unittest.mock import Mock, MagicMock


def test_collector_creation():
    """Test DataCollector instantiation."""
    from shared.collector.collector import DataCollector
    from shared.collector.adapter import MockAPIAdapter

    adapter = MockAPIAdapter()
    collector = DataCollector(adapter)

    assert collector.adapter is adapter
    assert collector._message_count == 0


def test_collector_tick_callback():
    """Test tick callback publishes to stream."""
    from shared.collector.collector import DataCollector
    from shared.collector.adapter import MockAPIAdapter
    from shared.collector.models import TickData

    adapter = MockAPIAdapter()
    collector = DataCollector(adapter)

    # Mock the publisher
    collector.publisher = Mock()
    collector.publisher.publish = Mock()

    tick = TickData(
        symbol="TEST",
        timestamp=1705300800.0,
        bid_price_1=100.0,
        bid_qty_1=10,
        ask_price_1=100.1,
        ask_qty_1=10,
    )

    collector._on_tick(tick)

    assert collector._message_count == 1
    collector.publisher.publish.assert_called_once()
