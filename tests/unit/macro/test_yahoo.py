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


def _two_row_hist(last: float, prev: float) -> MagicMock:
    hist = MagicMock()
    hist.empty = False
    hist.__len__.return_value = 2
    hist.iloc.__getitem__.side_effect = lambda idx: {
        -1: {"Close": last},
        -2: {"Close": prev},
    }[idx]
    return hist


_PREMARKET_MAP = {
    "es_futures": "ES=F",
    "nq_futures": "NQ=F",
    "sox": "^SOX",
    "usdkrw_realtime": "KRW=X",
}


@patch("shared.macro.sources.yahoo.yf")
def test_yahoo_us_close_uses_legacy_map_by_default(mock_yf):
    """No ticker_map arg → exact legacy symbols requested (backward compat)."""
    mock_yf.Ticker.return_value.history.return_value = _two_row_hist(5100.0, 5050.0)

    import asyncio

    asyncio.run(YahooMacroSource().fetch_us_close_snapshot())
    requested = [c.args[0] for c in mock_yf.Ticker.call_args_list]
    assert requested == ["^GSPC", "^IXIC", "^VIX", "DX-Y.NYB", "^TNX"]


@patch("shared.macro.sources.yahoo.yf")
def test_yahoo_us_close_honors_config_ticker_map(mock_yf):
    """Symbol overrides are config-only — the injected map wins."""
    mock_yf.Ticker.return_value.history.return_value = _two_row_hist(100.0, 99.0)

    import asyncio

    custom = {
        "sp500": "TEST-SPX",
        "nasdaq": "^IXIC",
        "vix": "^VIX",
        "dxy": "DX-Y.NYB",
        "us10y": "^TNX",
    }
    snap = asyncio.run(YahooMacroSource(ticker_map=custom).fetch_us_close_snapshot())
    requested = [c.args[0] for c in mock_yf.Ticker.call_args_list]
    assert requested[0] == "TEST-SPX"
    assert snap.sp500_close == 100.0


@patch("shared.macro.sources.yahoo.yf")
def test_yahoo_fetches_premarket_snapshot(mock_yf):
    mock_yf.Ticker.return_value.history.return_value = _two_row_hist(6000.0, 5940.0)

    import asyncio

    src = YahooMacroSource(ticker_map={**_PREMARKET_MAP, "sp500": "^GSPC"})
    snap = asyncio.run(src.fetch_premarket_snapshot())

    assert snap.session == "premarket"
    assert "yahoo" in snap.collected_from
    # All four pre-market fields carry close + change_pct.
    expected_pct = (6000.0 - 5940.0) / 5940.0 * 100.0
    for prefix in ("es_futures", "nq_futures", "sox", "usdkrw_realtime"):
        assert getattr(snap, prefix) == 6000.0
        assert abs(getattr(snap, f"{prefix}_change_pct") - expected_pct) < 1e-9
    # Only pre-market tickers were requested — not the us_close set.
    requested = [c.args[0] for c in mock_yf.Ticker.call_args_list]
    assert requested == ["ES=F", "NQ=F", "^SOX", "KRW=X"]
    # us_close fields untouched (additive contract).
    assert snap.sp500_close is None
    assert snap.eurex_kospi_close is None


@patch("shared.macro.sources.yahoo.yf")
def test_yahoo_premarket_missing_map_keys_yield_none(mock_yf):
    """Legacy 5-symbol fallback map has no pre-market keys → graceful None."""
    mock_yf.Ticker.return_value.history.return_value = _two_row_hist(6000.0, 5940.0)

    import asyncio

    snap = asyncio.run(YahooMacroSource().fetch_premarket_snapshot())
    assert snap.session == "premarket"
    assert snap.es_futures is None
    assert snap.nq_futures is None
    assert snap.sox is None
    assert snap.usdkrw_realtime is None
    mock_yf.Ticker.assert_not_called()
