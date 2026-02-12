"""Shared fixtures for KIS WebSocket tests."""
import pytest
from unittest.mock import MagicMock, patch
from shared.kis.auth import KISAuthConfig


@pytest.fixture
def mock_config():
    """Create mock KIS auth config."""
    return KISAuthConfig(
        app_key="test_app_key",
        app_secret="test_app_secret",
        is_real=False,
    )


@pytest.fixture
def sample_orderbook_data():
    """Sample H0IFASP0 (orderbook) message data.

    42+ fields separated by ^
    Field layout:
        0-1: symbol, time
        2-11: ask prices 1-10
        12-21: ask quantities 1-10
        22-31: bid prices 1-10
        32-41: bid quantities 1-10
    """
    fields = [""] * 42
    # Ask prices (fields 2-6)
    fields[2] = "330.50"  # ask_price_1
    fields[3] = "330.55"  # ask_price_2
    fields[4] = "330.60"  # ask_price_3
    fields[5] = "330.65"  # ask_price_4
    fields[6] = "330.70"  # ask_price_5
    # Ask quantities (fields 12-16)
    fields[12] = "100"  # ask_qty_1
    fields[13] = "150"  # ask_qty_2
    fields[14] = "200"  # ask_qty_3
    fields[15] = "250"  # ask_qty_4
    fields[16] = "300"  # ask_qty_5
    # Bid prices (fields 22-26)
    fields[22] = "330.45"  # bid_price_1
    fields[23] = "330.40"  # bid_price_2
    fields[24] = "330.35"  # bid_price_3
    fields[25] = "330.30"  # bid_price_4
    fields[26] = "330.25"  # bid_price_5
    # Bid quantities (fields 32-36)
    fields[32] = "120"  # bid_qty_1
    fields[33] = "180"  # bid_qty_2
    fields[34] = "220"  # bid_qty_3
    fields[35] = "280"  # bid_qty_4
    fields[36] = "320"  # bid_qty_5

    return "^".join(fields)


@pytest.fixture
def sample_trade_data():
    """Sample H0IFCNT0 (trade) message data.

    19+ fields separated by ^
    Field layout (corrected):
        0: 종목코드
        1: 체결시간
        5: 현재가 (current_price)
        6: 시가 (open_price)
        7: 고가 (high_price)
        8: 저가 (low_price)
        9: 체결수량 (tick_volume)
        10: 누적체결수량 (cumulative_volume)
        18: 미결제약정 (open_interest)
    """
    fields = [""] * 19
    fields[0] = "101V01"
    fields[1] = "093000"
    fields[5] = "330.25"  # current_price
    fields[6] = "329.50"  # open_price
    fields[7] = "331.00"  # high_price
    fields[8] = "329.00"  # low_price
    fields[9] = "5"  # tick_volume
    fields[10] = "15000"  # cumulative_volume
    fields[18] = "25000"  # open_interest

    return "^".join(fields)


@pytest.fixture
def mock_websocket_app():
    """Create mock WebSocket application."""
    ws = MagicMock()
    ws.send = MagicMock()
    ws.close = MagicMock()
    ws.run_forever = MagicMock()
    return ws


@pytest.fixture
def mock_adapter(mock_config):
    """Create mock KIS WebSocket adapter without actual connection."""
    with patch('shared.kis.websocket.websocket.WebSocketApp'):
        from shared.kis.websocket import KISWebSocketAdapter
        adapter = KISWebSocketAdapter(mock_config)
        return adapter
