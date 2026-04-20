from unittest.mock import MagicMock, patch

import pytest

from shared.macro.sources.yahoo import YahooMacroSource


@patch("shared.macro.sources.yahoo.yf")
def test_yahoo_fetches_us_close_snapshot(mock_yf):
    # Mock yfinance Ticker().history() return: a tiny DataFrame-like
    mock_hist = MagicMock()
    # Act like a 2-row DataFrame: iloc[-1] and iloc[-2]
    mock_hist.empty = False
    mock_hist.__len__.return_value = 2
    mock_hist.iloc.__getitem__.side_effect = lambda idx: {
        -1: {"Close": 5100.0},
        -2: {"Close": 5050.0},
    }[idx]
    mock_yf.Ticker.return_value.history.return_value = mock_hist

    src = YahooMacroSource()
    snap = pytest.run(src.fetch_us_close_snapshot()) if False else None  # see below

    # Call synchronously since YahooMacroSource wraps sync yfinance
    import asyncio

    snap = asyncio.run(src.fetch_us_close_snapshot())
    assert snap.session == "overnight_us_close"
    assert snap.sp500_close == 5100.0
    assert abs(snap.sp500_change_pct - (5100 - 5050) / 5050 * 100) < 1e-6
    assert "yahoo" in snap.collected_from


@patch("shared.macro.sources.yahoo.yf")
def test_yahoo_returns_none_fields_on_empty_history(mock_yf):
    mock_hist = MagicMock()
    mock_hist.empty = True
    mock_yf.Ticker.return_value.history.return_value = mock_hist

    import asyncio

    src = YahooMacroSource()
    snap = asyncio.run(src.fetch_us_close_snapshot())
    assert snap.sp500_close is None
    assert snap.nasdaq_close is None
