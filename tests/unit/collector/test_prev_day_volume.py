"""Tests for PrevDayVolumeCache."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from shared.collector.prev_day_volume import PrevDayVolumeCache

MODULE = "shared.collector.prev_day_volume"


@pytest.fixture
def mock_ohlcv():
    """Mock pykrx data with volume column."""
    return pd.DataFrame(
        {"거래량": [10_000_000, 5_000_000, 800_000]},
        index=["005930", "000660", "035720"],
    )


def _make_mock_stock(ohlcv_df):
    mock_stock = MagicMock()
    mock_stock.get_market_ohlcv.return_value = ohlcv_df
    return mock_stock


class TestPrevDayVolumeCache:

    def test_warm_all_loads_volumes(self, mock_ohlcv):
        cache = PrevDayVolumeCache()
        mock_stock = _make_mock_stock(mock_ohlcv)

        with patch(f"{MODULE}._get_pykrx_stock", return_value=mock_stock):
            with patch(f"{MODULE}._last_trading_date_str", return_value="20260216"):
                loaded = cache.warm_all()

        # KOSPI + KOSDAQ = 3 + 3 = 6 (same mock for both)
        assert loaded == 6
        assert cache.get("005930") == 10_000_000
        assert cache.get("000660") == 5_000_000

    def test_get_returns_zero_for_unknown(self):
        cache = PrevDayVolumeCache()
        assert cache.get("999999") == 0

    def test_build_metadata_includes_only_known_codes(self):
        cache = PrevDayVolumeCache()
        cache._volumes = {"005930": 10_000_000, "000660": 5_000_000}

        meta = cache.build_metadata(["005930", "UNKNOWN"])
        assert "005930" in meta
        assert meta["005930"] == {"prev_day_volume": 10_000_000}
        assert "UNKNOWN" not in meta

    def test_ensure_fills_missing_codes(self):
        cache = PrevDayVolumeCache()
        cache._date = "20260216"

        single_df = pd.DataFrame({"거래량": [3_000_000]}, index=["123456"])
        mock_stock = _make_mock_stock(single_df)

        with patch(f"{MODULE}._get_pykrx_stock", return_value=mock_stock):
            filled = cache.ensure(["123456"])

        assert filled == 1
        assert cache.get("123456") == 3_000_000

    def test_ensure_skips_already_cached(self):
        cache = PrevDayVolumeCache()
        cache._volumes["005930"] = 10_000_000

        filled = cache.ensure(["005930"])
        assert filled == 0

    def test_warm_all_handles_import_error(self):
        cache = PrevDayVolumeCache()

        with patch(f"{MODULE}._get_pykrx_stock", side_effect=ImportError("no pykrx")):
            loaded = cache.warm_all()

        assert loaded == 0

    def test_date_property(self):
        cache = PrevDayVolumeCache()
        assert cache.date is None
        cache._date = "20260216"
        assert cache.date == "20260216"

    def test_len(self):
        cache = PrevDayVolumeCache()
        assert len(cache) == 0

        cache._volumes = {"005930": 10_000_000, "000660": 5_000_000, "035720": 800_000}
        assert len(cache) == 3

    def test_build_metadata_excludes_zero_volume(self):
        cache = PrevDayVolumeCache()
        cache._volumes = {"005930": 10_000_000, "000000": 0}

        meta = cache.build_metadata(["005930", "000000"])
        assert "005930" in meta
        assert "000000" not in meta


class TestPrevDayVolumeCacheAsync:
    """Test async wrappers for PrevDayVolumeCache."""

    @pytest.mark.asyncio
    async def test_warm_all_async_delegates(self, mock_ohlcv):
        cache = PrevDayVolumeCache()
        mock_stock = _make_mock_stock(mock_ohlcv)

        with patch(f"{MODULE}._get_pykrx_stock", return_value=mock_stock):
            with patch(f"{MODULE}._last_trading_date_str", return_value="20260216"):
                loaded = await cache.warm_all_async()

        assert loaded == 6
        assert cache.get("005930") == 10_000_000

    @pytest.mark.asyncio
    async def test_ensure_async_delegates(self):
        cache = PrevDayVolumeCache()
        cache._date = "20260216"

        single_df = pd.DataFrame({"거래량": [3_000_000]}, index=["123456"])
        mock_stock = _make_mock_stock(single_df)

        with patch(f"{MODULE}._get_pykrx_stock", return_value=mock_stock):
            filled = await cache.ensure_async(["123456"])

        assert filled == 1
        assert cache.get("123456") == 3_000_000
