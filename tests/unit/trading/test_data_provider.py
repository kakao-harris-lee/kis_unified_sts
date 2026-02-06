"""Tests for services/trading/data_provider.py"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock


class TestDataProviderConfig:
    """DataProviderConfig tests"""

    def test_default_values(self):
        """Test default configuration values"""
        from services.trading.data_provider import DataProviderConfig

        config = DataProviderConfig()
        assert config.cache_ttl_seconds == 1.0
        assert config.batch_size == 20
        assert config.fetch_timeout_seconds == 5.0
        assert config.mock_seed is None

    def test_validation_passes(self):
        """Test valid configuration passes"""
        from services.trading.data_provider import DataProviderConfig

        config = DataProviderConfig(
            cache_ttl_seconds=0.5,
            batch_size=10,
            fetch_timeout_seconds=2.0,
        )
        assert config.cache_ttl_seconds == 0.5

    def test_validation_cache_ttl_too_low(self):
        """Test cache_ttl_seconds below minimum raises"""
        from services.trading.data_provider import DataProviderConfig

        with pytest.raises(ValueError, match="cache_ttl_seconds"):
            DataProviderConfig(cache_ttl_seconds=0.01)

    def test_validation_cache_ttl_too_high(self):
        """Test cache_ttl_seconds above maximum raises"""
        from services.trading.data_provider import DataProviderConfig

        with pytest.raises(ValueError, match="cache_ttl_seconds"):
            DataProviderConfig(cache_ttl_seconds=500.0)

    def test_validation_batch_size(self):
        """Test batch_size validation"""
        from services.trading.data_provider import DataProviderConfig

        with pytest.raises(ValueError, match="batch_size"):
            DataProviderConfig(batch_size=0)

        with pytest.raises(ValueError, match="batch_size"):
            DataProviderConfig(batch_size=200)

    def test_from_dict(self):
        """Test from_dict factory method"""
        from services.trading.data_provider import DataProviderConfig

        config = DataProviderConfig.from_dict({
            "cache_ttl_seconds": 2.0,
            "batch_size": 15,
            "mock_seed": 42,
        })
        assert config.cache_ttl_seconds == 2.0
        assert config.batch_size == 15
        assert config.mock_seed == 42

    def test_from_dict_type_validation(self):
        """Test from_dict type validation"""
        from services.trading.data_provider import DataProviderConfig

        with pytest.raises(TypeError, match="cache_ttl_seconds"):
            DataProviderConfig.from_dict({"cache_ttl_seconds": "invalid"})


class TestMarketDataCache:
    """MarketDataCache tests"""

    def test_is_stale_fresh(self):
        """Test fresh cache is not stale"""
        from services.trading.data_provider import MarketDataCache

        cache = MarketDataCache(
            symbol="005930",
            data={"close": 71000},
            fetched_at=datetime.now(),
        )
        assert cache.is_stale(1.0) is False

    def test_is_stale_expired(self):
        """Test expired cache is stale"""
        from services.trading.data_provider import MarketDataCache

        cache = MarketDataCache(
            symbol="005930",
            data={"close": 71000},
            fetched_at=datetime.now() - timedelta(seconds=10),
        )
        assert cache.is_stale(1.0) is True


class TestMarketDataProvider:
    """MarketDataProvider tests"""

    def test_init_default(self):
        """Test default initialization"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider()
        assert provider.symbols == []
        assert provider.config.cache_ttl_seconds == 1.0

    def test_init_with_symbols(self):
        """Test initialization with symbols"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider(symbols=["005930", "000660"])
        assert len(provider.symbols) == 2
        assert "005930" in provider.symbols

    def test_add_symbols(self):
        """Test adding symbols"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider()
        provider.add_symbols(["005930", "000660"])
        assert len(provider.symbols) == 2

        # Adding same symbol doesn't duplicate
        provider.add_symbols(["005930"])
        assert len(provider.symbols) == 2

    def test_remove_symbol(self):
        """Test removing symbol"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider(symbols=["005930", "000660"])
        provider.remove_symbol("005930")
        assert "005930" not in provider.symbols
        assert "000660" in provider.symbols

    @pytest.mark.asyncio
    async def test_get_data_empty_symbols(self):
        """Test get_data with no symbols returns empty"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider()
        data = await provider.get_data()
        assert data == {}

    @pytest.mark.asyncio
    async def test_get_data_generates_mock(self):
        """Test get_data generates mock data when no client"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider(symbols=["005930"])
        data = await provider.get_data()

        assert "005930" in data
        assert "close" in data["005930"]
        assert "volume" in data["005930"]

    @pytest.mark.asyncio
    async def test_get_data_caching(self):
        """Test data is cached and reused"""
        from services.trading.data_provider import MarketDataProvider, DataProviderConfig

        config = DataProviderConfig(cache_ttl_seconds=10.0, mock_seed=42)
        provider = MarketDataProvider(symbols=["005930"], config=config)

        # First call
        data1 = await provider.get_data()
        # Second call should return cached
        data2 = await provider.get_data()

        assert data1["005930"]["close"] == data2["005930"]["close"]

    @pytest.mark.asyncio
    async def test_get_data_force_refresh(self):
        """Test force_refresh bypasses cache"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider(symbols=["005930"])

        data1 = await provider.get_data()
        data2 = await provider.get_data(force_refresh=True)

        # Values may differ due to random generation
        assert "close" in data2["005930"]

    @pytest.mark.asyncio
    async def test_get_single(self):
        """Test get_single method"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider(symbols=["005930"])
        data = await provider.get_single("005930")

        assert data is not None
        assert "close" in data

    @pytest.mark.asyncio
    async def test_get_with_indicators(self):
        """Test get_with_indicators includes cached indicators"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider(symbols=["005930"])

        # Fetch data first
        await provider.get_data()

        # Update indicators
        provider.update_indicators("005930", {"rsi": 45.0, "bb_lower": 70000})

        # Get with indicators
        data = await provider.get_with_indicators("005930", ["rsi", "bb_lower"])

        assert data.get("rsi") == 45.0
        assert data.get("bb_lower") == 70000

    def test_get_cache_stats(self):
        """Test cache statistics"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider(symbols=["005930", "000660"])
        stats = provider.get_cache_stats()

        assert stats["total_symbols"] == 2
        assert stats["cached_symbols"] == 0

    def test_clear_cache(self):
        """Test cache clearing"""
        from services.trading.data_provider import MarketDataProvider

        provider = MarketDataProvider(symbols=["005930"])
        provider.clear_cache()

        stats = provider.get_cache_stats()
        assert stats["cached_symbols"] == 0

    @pytest.mark.asyncio
    async def test_mock_seed_reproducibility(self):
        """Test mock data is reproducible with seed"""
        from services.trading.data_provider import MarketDataProvider, DataProviderConfig

        config1 = DataProviderConfig(mock_seed=42)
        provider1 = MarketDataProvider(symbols=["005930"], config=config1)

        config2 = DataProviderConfig(mock_seed=42)
        provider2 = MarketDataProvider(symbols=["005930"], config=config2)

        data1 = await provider1.get_data()
        data2 = await provider2.get_data()

        assert data1["005930"]["close"] == data2["005930"]["close"]


class TestMarketDataSourceProtocol:
    """MarketDataSource protocol tests"""

    @pytest.mark.asyncio
    async def test_custom_data_source(self):
        """Test with custom data source implementing protocol"""
        from services.trading.data_provider import MarketDataProvider

        class CustomSource:
            async def get_current_price(self, symbol: str) -> dict:
                return {"close": 99999, "symbol": symbol}

        source = CustomSource()
        provider = MarketDataProvider(
            symbols=["TEST"],
            data_source=source,
        )

        data = await provider.get_data()
        assert data["TEST"]["close"] == 99999

    @pytest.mark.asyncio
    async def test_parallel_fetching(self):
        """Test parallel fetching from data source"""
        from services.trading.data_provider import MarketDataProvider, DataProviderConfig

        call_times = []

        class SlowSource:
            async def get_current_price(self, symbol: str) -> dict:
                call_times.append(datetime.now())
                await asyncio.sleep(0.01)
                return {"close": 50000, "symbol": symbol}

        config = DataProviderConfig(batch_size=10)
        provider = MarketDataProvider(
            symbols=["A", "B", "C"],
            config=config,
            data_source=SlowSource(),
        )

        start = datetime.now()
        data = await provider.get_data()
        elapsed = (datetime.now() - start).total_seconds()

        # Should be faster than sequential (3 * 0.01 = 0.03s)
        # With staggered parallel (50ms apart), ~0.12s for 3 symbols
        assert len(data) == 3
        # Allow for stagger overhead (3 * 50ms + 10ms API + margin)
        assert elapsed < 0.3
