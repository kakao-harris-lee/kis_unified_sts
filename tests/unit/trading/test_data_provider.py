"""Tests for services/trading/data_provider.py"""

import asyncio
import pytest
from datetime import datetime, timedelta


class TestDataProviderConfig:
    """DataProviderConfig tests"""

    def test_default_values(self):
        """Test default configuration values"""
        from services.trading.data_provider import DataProviderConfig

        config = DataProviderConfig()
        assert config.cache_ttl_seconds == 1.0
        assert config.batch_size == 20
        assert config.fetch_timeout_seconds == 5.0
        assert config.staleness_threshold_seconds == 10.0
        assert config.rest_fallback_max_symbols is None
        assert config.startup_grace_seconds == 60.0
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

        config = DataProviderConfig.from_dict(
            {
                "cache_ttl_seconds": 2.0,
                "batch_size": 15,
                "staleness_threshold_seconds": 12.0,
                "min_fresh_ratio": 0.25,
                "startup_grace_seconds": 45.0,
                "rest_fallback_max_symbols": 10,
                "mock_seed": 42,
            }
        )
        assert config.cache_ttl_seconds == 2.0
        assert config.batch_size == 15
        assert config.staleness_threshold_seconds == 12.0
        assert config.min_fresh_ratio == 0.25
        assert config.startup_grace_seconds == 45.0
        assert config.rest_fallback_max_symbols == 10
        assert config.mock_seed == 42

    def test_from_dict_type_validation(self):
        """Test from_dict type validation"""
        from services.trading.data_provider import DataProviderConfig

        with pytest.raises(TypeError, match="cache_ttl_seconds"):
            DataProviderConfig.from_dict({"cache_ttl_seconds": "invalid"})

        with pytest.raises(TypeError, match="min_fresh_ratio"):
            DataProviderConfig.from_dict({"min_fresh_ratio": "invalid"})

        with pytest.raises(TypeError, match="startup_grace_seconds"):
            DataProviderConfig.from_dict({"startup_grace_seconds": "invalid"})


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
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
        )

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

        _ = await provider.get_data()
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

    def test_get_cache_stats_uses_current_symbols_only(self):
        """Freshness stats should ignore old cache entries for removed symbols."""
        from services.trading.data_provider import (
            DataProviderConfig,
            MarketDataCache,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            symbols=["005930", "000660"],
            config=DataProviderConfig(cache_ttl_seconds=10.0),
        )
        now = datetime.now()
        provider._cache["005930"] = MarketDataCache(
            symbol="005930",
            data={"close": 70000},
            fetched_at=now,
        )
        provider._cache["000660"] = MarketDataCache(
            symbol="000660",
            data={"close": 120000},
            fetched_at=now - timedelta(seconds=30),
        )
        provider._cache["OLD001"] = MarketDataCache(
            symbol="OLD001",
            data={"close": 1},
            fetched_at=now - timedelta(seconds=30),
        )

        stats = provider.get_cache_stats()

        assert stats["total_symbols"] == 2
        assert stats["cached_symbols"] == 2
        assert stats["fresh_count"] == 1
        assert stats["stale_count"] == 1
        assert stats["cache_entries"] == 3

    def test_get_cache_stats_uses_operational_freshness_threshold(self):
        """Operational freshness should not flap on short WebSocket cache TTL."""
        from services.trading.data_provider import (
            DataProviderConfig,
            MarketDataCache,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            symbols=["005930", "000660"],
            config=DataProviderConfig(
                cache_ttl_seconds=2.0,
                staleness_threshold_seconds=10.0,
            ),
        )
        now = datetime.now()
        provider._cache["005930"] = MarketDataCache(
            symbol="005930",
            data={"close": 70000},
            fetched_at=now - timedelta(seconds=5),
        )
        provider._cache["000660"] = MarketDataCache(
            symbol="000660",
            data={"close": 120000},
            fetched_at=now - timedelta(seconds=12),
        )

        stats = provider.get_cache_stats()

        assert stats["freshness_threshold_seconds"] == 10.0
        assert stats["fresh_count"] == 1
        assert stats["stale_count"] == 1

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
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
        )

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
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
        )

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


class TestFailoverLogic:
    """MarketDataProvider failover and recovery tests"""

    def test_initial_mode_is_websocket(self):
        """Test provider initializes in WebSocket mode"""
        from services.trading.data_provider import MarketDataProvider, DataSourceMode

        provider = MarketDataProvider()
        assert provider.current_mode == DataSourceMode.WEBSOCKET
        assert not provider.is_in_failover_mode

    def test_failover_state_properties(self):
        """Test failover state properties are readable"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
        )

        config = DataProviderConfig(
            health_check_interval_seconds=5.0,
            rest_poll_interval_seconds=5.0,
        )
        provider = MarketDataProvider(config=config)

        stats = provider.get_cache_stats()
        assert "current_mode" in stats
        assert "is_in_failover" in stats
        assert "health_check_active" in stats
        assert "fallback_poll_active" in stats
        assert stats["current_mode"] == "websocket"
        assert stats["is_in_failover"] is False

    @pytest.mark.asyncio
    async def test_failover_to_rest(self):
        """Test failover from WebSocket to REST mode"""
        from services.trading.data_provider import MarketDataProvider, DataSourceMode

        provider = MarketDataProvider(symbols=["005930"])

        # Initial state
        assert provider.current_mode == DataSourceMode.WEBSOCKET

        # Trigger failover
        await provider._failover_to_rest()

        # Should now be in REST fallback mode
        assert provider.current_mode == DataSourceMode.REST_FALLBACK
        assert provider.is_in_failover_mode

    @pytest.mark.asyncio
    async def test_failover_idempotency(self):
        """Test failover is idempotent (calling twice has no effect)"""
        from services.trading.data_provider import MarketDataProvider, DataSourceMode

        provider = MarketDataProvider()

        # First failover
        await provider._failover_to_rest()
        assert provider.current_mode == DataSourceMode.REST_FALLBACK

        # Second failover should be no-op
        await provider._failover_to_rest()
        assert provider.current_mode == DataSourceMode.REST_FALLBACK

    @pytest.mark.asyncio
    async def test_recovery_to_websocket(self):
        """Test recovery from REST fallback to WebSocket mode"""
        from services.trading.data_provider import MarketDataProvider, DataSourceMode

        class HealthySource:
            async def get_current_price(self, symbol: str) -> dict:
                return {"close": 50000}

            def is_healthy(self) -> bool:
                return True

        provider = MarketDataProvider(
            symbols=["005930"],
            data_source=HealthySource(),
        )

        # Failover to REST
        await provider._failover_to_rest()
        assert provider.current_mode == DataSourceMode.REST_FALLBACK

        # Recover to WebSocket
        await provider._recover_to_websocket()
        assert provider.current_mode == DataSourceMode.WEBSOCKET
        assert not provider.is_in_failover_mode

    @pytest.mark.asyncio
    async def test_recovery_requires_healthy_source(self):
        """Test recovery only happens if data source is healthy"""
        from services.trading.data_provider import MarketDataProvider, DataSourceMode

        class UnhealthySource:
            async def get_current_price(self, symbol: str) -> dict:
                return {"close": 50000}

            def is_healthy(self) -> bool:
                return False

        provider = MarketDataProvider(
            symbols=["005930"],
            data_source=UnhealthySource(),
        )

        # Failover to REST
        await provider._failover_to_rest()
        assert provider.current_mode == DataSourceMode.REST_FALLBACK

        # Attempt recovery (should fail because source is unhealthy)
        await provider._recover_to_websocket()
        # Should remain in REST fallback
        assert provider.current_mode == DataSourceMode.REST_FALLBACK

    @pytest.mark.asyncio
    async def test_recovery_idempotency(self):
        """Test recovery is idempotent (calling twice has no effect)"""
        from services.trading.data_provider import MarketDataProvider, DataSourceMode

        class HealthySource:
            def is_healthy(self) -> bool:
                return True

        provider = MarketDataProvider(data_source=HealthySource())

        # Already in WebSocket mode
        assert provider.current_mode == DataSourceMode.WEBSOCKET

        # Recovery should be no-op
        await provider._recover_to_websocket()
        assert provider.current_mode == DataSourceMode.WEBSOCKET

    @pytest.mark.asyncio
    async def test_failover_with_telegram_alerts(self):
        """Test failover sends Telegram alert when configured"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
        )
        from unittest.mock import AsyncMock

        telegram_notifier = AsyncMock()
        config = DataProviderConfig(send_telegram_alerts=True)

        provider = MarketDataProvider(
            config=config,
            telegram_notifier=telegram_notifier,
        )

        await provider._failover_to_rest()

        # Should have sent failover alert
        telegram_notifier.send_message.assert_called_once()
        call_args = telegram_notifier.send_message.call_args
        message = call_args[0][0]
        assert "WebSocket" in message
        assert "REST" in message

    @pytest.mark.asyncio
    async def test_recovery_with_telegram_alerts(self):
        """Test recovery sends Telegram alert when configured"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
        )
        from unittest.mock import AsyncMock

        class HealthySource:
            def is_healthy(self) -> bool:
                return True

        telegram_notifier = AsyncMock()
        config = DataProviderConfig(send_telegram_alerts=True)

        provider = MarketDataProvider(
            config=config,
            data_source=HealthySource(),
            telegram_notifier=telegram_notifier,
        )

        # Failover then recover
        await provider._failover_to_rest()
        telegram_notifier.reset_mock()

        await provider._recover_to_websocket()

        # Should have sent recovery alert
        telegram_notifier.send_message.assert_called_once()
        call_args = telegram_notifier.send_message.call_args
        message = call_args[0][0]
        assert "복구" in message or "recovery" in message.lower()

    @pytest.mark.asyncio
    async def test_telegram_alerts_disabled(self):
        """Test Telegram alerts are not sent when disabled"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
        )
        from unittest.mock import AsyncMock

        telegram_notifier = AsyncMock()
        config = DataProviderConfig(send_telegram_alerts=False)

        provider = MarketDataProvider(
            config=config,
            telegram_notifier=telegram_notifier,
        )

        await provider._failover_to_rest()

        # Should not have sent alert
        telegram_notifier.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_telegram_alert_failure_does_not_break_failover(self):
        """Test failover continues even if Telegram alert fails"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
            DataSourceMode,
        )
        from unittest.mock import AsyncMock

        telegram_notifier = AsyncMock()
        telegram_notifier.send_message.side_effect = Exception("Telegram API error")

        config = DataProviderConfig(send_telegram_alerts=True)

        provider = MarketDataProvider(
            config=config,
            telegram_notifier=telegram_notifier,
        )

        # Failover should succeed despite Telegram error
        await provider._failover_to_rest()
        assert provider.current_mode == DataSourceMode.REST_FALLBACK

    @pytest.mark.asyncio
    async def test_health_check_loop_triggers_failover(self):
        """Test health check loop triggers failover when source becomes unhealthy"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
            DataSourceMode,
        )

        class ToggleHealthSource:
            def get_health_status(self) -> dict:
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": 11.0,
                    "fresh_symbol_count": 1,
                    "symbol_count": 1,
                }

        config = DataProviderConfig(
            health_check_interval_seconds=0.5,
            staleness_threshold_seconds=10.0,
        )
        source = ToggleHealthSource()
        provider = MarketDataProvider(config=config, data_source=source)

        # Start health check task
        health_task = asyncio.create_task(provider._health_check_loop())

        # Wait for first health check cycle (interval + processing time)
        await asyncio.sleep(0.7)

        # Should have triggered failover because source is unhealthy
        assert provider.current_mode == DataSourceMode.REST_FALLBACK

        # Cleanup
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_background_tasks_starts_health_monitoring(self):
        """Test lifecycle helper starts health monitoring when supported."""
        from services.trading.data_provider import MarketDataProvider

        class HealthySource:
            def is_healthy(self) -> bool:
                return True

        provider = MarketDataProvider(data_source=HealthySource())

        await provider.start_background_tasks()

        assert provider._health_check_task is not None
        assert not provider._health_check_task.done()

        await provider.stop_background_tasks()
        assert provider._health_check_task is None

    @pytest.mark.asyncio
    async def test_failover_mode_prefers_rest_client_over_websocket_source(self):
        """Test REST fallback reads from KIS client instead of stale WebSocket cache."""
        from services.trading.data_provider import MarketDataProvider

        class WebSocketSource:
            async def get_current_price(self, symbol: str) -> dict:
                return {"close": 100.0, "source": "websocket"}

            def is_healthy(self) -> bool:
                return False

        class RestClient:
            async def get_current_price(self, symbol: str) -> dict:
                return {"close": 200.0, "source": "rest"}

        provider = MarketDataProvider(
            symbols=["005930"],
            data_source=WebSocketSource(),
            kis_client=RestClient(),
        )

        websocket_data = await provider.get_data(force_refresh=True)
        assert websocket_data["005930"]["source"] == "websocket"

        await provider._failover_to_rest()
        rest_data = await provider.get_data(force_refresh=True)

        assert rest_data["005930"]["source"] == "rest"

        await provider.stop_background_tasks()

    @pytest.mark.asyncio
    async def test_health_check_loop_triggers_recovery(self):
        """Test health check loop triggers recovery when source becomes healthy again"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
            DataSourceMode,
        )

        class ToggleHealthSource:
            def get_health_status(self) -> dict:
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": 1.0,
                    "fresh_symbol_count": 1,
                    "symbol_count": 1,
                }

        config = DataProviderConfig(
            health_check_interval_seconds=0.5,
            staleness_threshold_seconds=10.0,
        )
        source = ToggleHealthSource()
        provider = MarketDataProvider(config=config, data_source=source)

        # Manually failover first
        await provider._failover_to_rest()
        assert provider.current_mode == DataSourceMode.REST_FALLBACK

        # Start health check task
        health_task = asyncio.create_task(provider._health_check_loop())

        # Wait for health check cycle (interval + processing time)
        await asyncio.sleep(0.7)

        # Should have recovered because source is healthy
        assert provider.current_mode == DataSourceMode.WEBSOCKET

        # Cleanup
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_rest_poll_loop_fetches_data(self):
        """Test REST polling loop fetches data at regular intervals"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
        )

        fetch_count = []

        class CountingClient:
            async def get_current_price(self, symbol: str) -> dict:
                fetch_count.append(symbol)
                return {"close": 50000}

        config = DataProviderConfig(rest_poll_interval_seconds=0.5)
        provider = MarketDataProvider(
            symbols=["005930"],
            config=config,
            kis_client=CountingClient(),
        )

        # Enter REST fallback mode and start polling
        await provider._failover_to_rest()

        # Let polling run for a bit (enough for 2 cycles)
        await asyncio.sleep(1.2)

        # Should have fetched data at least twice
        assert len(fetch_count) >= 2

        # Cleanup
        if provider._fallback_poll_task:
            provider._fallback_poll_task.cancel()
            try:
                await provider._fallback_poll_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_rest_poll_loop_stops_after_recovery(self):
        """Test REST polling loop stops when recovering to WebSocket"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
            DataSourceMode,
        )

        class HealthySource:
            def is_healthy(self) -> bool:
                return True

        class DummyClient:
            async def get_current_price(self, symbol: str) -> dict:
                return {"close": 50000}

        config = DataProviderConfig(rest_poll_interval_seconds=0.5)
        provider = MarketDataProvider(
            symbols=["005930"],
            config=config,
            data_source=HealthySource(),
            kis_client=DummyClient(),
        )

        # Enter REST fallback mode
        await provider._failover_to_rest()
        assert provider._fallback_poll_task is not None

        # Let polling start
        await asyncio.sleep(0.1)

        # Recover to WebSocket
        await provider._recover_to_websocket()
        assert provider.current_mode == DataSourceMode.WEBSOCKET

        # Wait for task to finish cancelling
        await asyncio.sleep(0.2)

        # Poll task should be done/cancelled
        assert provider._fallback_poll_task.done()

    @pytest.mark.asyncio
    async def test_rest_poll_loop_handles_fetch_errors(self):
        """Test REST polling loop continues despite fetch errors"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
        )
        from shared.exceptions import NetworkError

        error_count = []
        success_count = []

        class FlakeyClient:
            def __init__(self):
                self.call_count = 0

            async def get_current_price(self, symbol: str) -> dict:
                self.call_count += 1
                if self.call_count == 1:
                    error_count.append(1)
                    raise NetworkError("Connection failed")
                success_count.append(1)
                return {"close": 50000}

        config = DataProviderConfig(rest_poll_interval_seconds=0.5)
        client = FlakeyClient()
        provider = MarketDataProvider(
            symbols=["005930"],
            config=config,
            kis_client=client,
        )

        # Enter REST fallback mode
        await provider._failover_to_rest()

        # Let polling run for a bit (should encounter error then recover)
        await asyncio.sleep(1.2)

        # Should have encountered error but continued
        assert len(error_count) >= 1
        assert len(success_count) >= 1

        # Cleanup
        if provider._fallback_poll_task:
            provider._fallback_poll_task.cancel()
            try:
                await provider._fallback_poll_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_health_check_with_no_data_source(self):
        """Test health check handles case with no data source gracefully"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
            DataSourceMode,
        )

        config = DataProviderConfig(health_check_interval_seconds=0.5)
        provider = MarketDataProvider(config=config)

        # Start health check (should not crash with no data source)
        health_task = asyncio.create_task(provider._health_check_loop())

        await asyncio.sleep(0.7)

        # Should remain in WebSocket mode
        assert provider.current_mode == DataSourceMode.WEBSOCKET

        # Cleanup
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_async_is_healthy_method(self):
        """Test health check handles async is_healthy() method"""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
            DataSourceMode,
        )

        class AsyncHealthSource:
            async def is_healthy(self) -> bool:
                return False

        config = DataProviderConfig(health_check_interval_seconds=0.5)
        provider = MarketDataProvider(config=config, data_source=AsyncHealthSource())

        # Start health check
        health_task = asyncio.create_task(provider._health_check_loop())

        await asyncio.sleep(0.7)

        # Should have triggered failover
        assert provider.current_mode == DataSourceMode.REST_FALLBACK

        # Cleanup
        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_health_check_uses_provider_staleness_threshold(self):
        """Feed health should respect the failover threshold configured on the provider."""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
            DataSourceMode,
        )

        class NearStaleSource:
            def get_health_status(self) -> dict:
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": 4.8,
                    "fresh_symbol_count": 1,
                    "symbol_count": 1,
                }

            def is_healthy(self) -> bool:
                return False

        provider = MarketDataProvider(
            config=DataProviderConfig(
                health_check_interval_seconds=0.5,
                staleness_threshold_seconds=10.0,
            ),
            data_source=NearStaleSource(),
        )

        health_task = asyncio.create_task(provider._health_check_loop())
        await asyncio.sleep(0.7)

        assert provider.current_mode == DataSourceMode.WEBSOCKET

        health_task.cancel()
        try:
            await health_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_sequential_fetch_continues_after_generic_symbol_error(self):
        """A generic KIS client exception should not abort the whole sequential batch."""
        from services.trading.data_provider import MarketDataProvider

        class FlakeySequentialSource:
            supports_parallel = False

            async def get_current_price(self, symbol: str) -> dict:
                if symbol == "005930":
                    raise Exception("KIS API Error 500")
                return {"code": symbol, "close": 123.0}

        provider = MarketDataProvider()
        data = await provider._fetch_from_source(
            ["005930", "000660"],
            FlakeySequentialSource(),
        )

        assert "005930" not in data
        assert data["000660"]["close"] == 123.0

    @pytest.mark.asyncio
    async def test_fetch_batch_preserves_cache_when_real_source_fails(self):
        """REST/source failures should keep the last real cache instead of generating mock data."""
        from services.trading.data_provider import (
            DataSourceMode,
            MarketDataProvider,
            MarketDataCache,
        )

        class FailingClient:
            supports_parallel = False

            async def get_current_price(self, symbol: str) -> dict:
                raise Exception("KIS API Error 500")

        provider = MarketDataProvider(symbols=["005930"], kis_client=FailingClient())
        provider._current_mode = DataSourceMode.REST_FALLBACK
        provider._cache["005930"] = MarketDataCache(
            symbol="005930",
            data={"code": "005930", "close": 71000.0},
            fetched_at=datetime.now(),
        )

        await provider._fetch_batch(["005930"])

        assert provider._cache["005930"].data["close"] == 71000.0

    def test_select_rest_poll_symbols_prefers_oldest_cache_and_limit(self):
        """REST fallback should poll the stalest symbols first when capped."""
        from services.trading.data_provider import (
            MarketDataProvider,
            DataProviderConfig,
            MarketDataCache,
        )

        provider = MarketDataProvider(
            symbols=["A", "B", "C"],
            config=DataProviderConfig(rest_fallback_max_symbols=2),
        )
        now = datetime.now()
        provider._cache["A"] = MarketDataCache(
            "A", {"close": 1}, now - timedelta(seconds=5)
        )
        provider._cache["B"] = MarketDataCache(
            "B", {"close": 1}, now - timedelta(seconds=10)
        )
        provider._cache["C"] = MarketDataCache(
            "C", {"close": 1}, now - timedelta(seconds=1)
        )

        assert provider._select_rest_poll_symbols() == ["B", "A"]

    def test_foreground_fetch_skips_when_rest_fallback_poller_active(self):
        """Market-data loop should not duplicate REST fallback polling."""
        from services.trading.data_provider import (
            DataProviderConfig,
            DataSourceMode,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            symbols=["A", "B"],
            config=DataProviderConfig(rest_fallback_max_symbols=1),
        )
        provider._current_mode = DataSourceMode.REST_FALLBACK
        provider._fallback_poll_task = type(
            "RunningTask",
            (),
            {"done": lambda self: False},
        )()

        assert provider._select_fetch_symbols_for_mode(["A", "B"]) == []

    def test_foreground_fetch_is_capped_when_rest_fallback_poller_inactive(self):
        """Manual fallback fetches should still respect the fallback cap."""
        from services.trading.data_provider import (
            DataProviderConfig,
            DataSourceMode,
            MarketDataCache,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            symbols=["A", "B", "C"],
            config=DataProviderConfig(rest_fallback_max_symbols=2),
        )
        provider._current_mode = DataSourceMode.REST_FALLBACK
        now = datetime.now()
        provider._cache["A"] = MarketDataCache("A", {}, now - timedelta(seconds=2))
        provider._cache["B"] = MarketDataCache("B", {}, now - timedelta(seconds=5))
        provider._cache["C"] = MarketDataCache("C", {}, now - timedelta(seconds=1))

        assert provider._select_fetch_symbols_for_mode(["A", "B", "C"]) == ["B", "A"]


class TestSilentStallGuard:
    """Regression: 2026-05-11 stock orchestrator stalled silently 13:09–13:35 KST.

    All 21 trade-target symbols stopped ticking but a few non-universe
    dip-candidate symbols kept producing ticks, keeping `_last_tick_ts`
    fresh.  The legacy `fresh_symbol_count <= 0` check returned healthy
    because `fresh_symbol_count` was > 0 (some symbols ticking).  No
    failover triggered → IndicatorEngine got 800s+ stale data → 0 signals
    → 0 trades for ~30 min.

    Fix (PR #218): add `min_fresh_ratio` config (default 0.5) so the
    health check fails when fewer than half the subscribed symbols are
    fresh, even if the overall `_last_tick_ts` is recent.
    """

    @pytest.mark.asyncio
    async def test_silent_stall_triggers_failover(self):
        """Repro of 2026-05-11 incident: 5 of 40 symbols fresh, but
        `_last_tick_ts` very recent.  Old behaviour: healthy.  New:
        unhealthy via min_fresh_ratio guard.
        """
        from services.trading.data_provider import (
            DataProviderConfig,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            config=DataProviderConfig(
                staleness_threshold_seconds=10.0,
                min_fresh_ratio=0.5,
            )
        )

        # Stub data source that returns the silent-stall pattern
        class _StaleDataSource:
            async def get_health_status(self):
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": 0.5,  # overall recent
                    "symbol_count": 40,
                    "fresh_symbol_count": 5,  # only 5/40 = 12.5% fresh
                    "stale_symbol_count": 35,
                }

        provider._data_source = _StaleDataSource()
        is_healthy, status = await provider._check_data_source_health()
        assert is_healthy is False
        assert status["fresh_symbol_count"] == 5

    @pytest.mark.asyncio
    async def test_above_threshold_remains_healthy(self):
        """30 of 40 symbols fresh (75%) > 50% threshold → healthy."""
        from services.trading.data_provider import (
            DataProviderConfig,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            config=DataProviderConfig(
                staleness_threshold_seconds=10.0,
                min_fresh_ratio=0.5,
            )
        )

        class _MostlyFreshSource:
            async def get_health_status(self):
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": 0.5,
                    "symbol_count": 40,
                    "fresh_symbol_count": 30,
                    "stale_symbol_count": 10,
                }

        provider._data_source = _MostlyFreshSource()
        is_healthy, _ = await provider._check_data_source_health()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_startup_grace_defers_low_ratio_failover(self):
        """Fresh-ratio guard should not fail during initial subscription warm-up."""
        import time

        from services.trading.data_provider import (
            DataProviderConfig,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            config=DataProviderConfig(
                staleness_threshold_seconds=10.0,
                min_fresh_ratio=0.5,
                startup_grace_seconds=60.0,
            )
        )
        provider._health_monitor_started_at = time.monotonic()

        class _OpeningWarmupSource:
            async def get_health_status(self):
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": 0.5,
                    "symbol_count": 25,
                    "fresh_symbol_count": 11,
                    "stale_symbol_count": 14,
                }

        provider._data_source = _OpeningWarmupSource()
        is_healthy, _ = await provider._check_data_source_health()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_low_ratio_fails_after_startup_grace(self):
        """After grace, the same low fresh ratio should still catch a real stall."""
        import time

        from services.trading.data_provider import (
            DataProviderConfig,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            config=DataProviderConfig(
                staleness_threshold_seconds=10.0,
                min_fresh_ratio=0.5,
                startup_grace_seconds=60.0,
            )
        )
        provider._health_monitor_started_at = time.monotonic() - 61.0

        class _SilentStallSource:
            async def get_health_status(self):
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": 0.5,
                    "symbol_count": 25,
                    "fresh_symbol_count": 11,
                    "stale_symbol_count": 14,
                }

        provider._data_source = _SilentStallSource()
        is_healthy, _ = await provider._check_data_source_health()
        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_startup_grace_defers_no_tick_yet(self):
        """Connected feed with no first tick yet should not fail immediately."""
        import time

        from services.trading.data_provider import (
            DataProviderConfig,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            config=DataProviderConfig(
                min_fresh_ratio=0.5,
                startup_grace_seconds=60.0,
            )
        )
        provider._health_monitor_started_at = time.monotonic()

        class _NoTickYetSource:
            async def get_health_status(self):
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": None,
                    "symbol_count": 25,
                    "fresh_symbol_count": 0,
                    "stale_symbol_count": 25,
                }

        provider._data_source = _NoTickYetSource()
        is_healthy, _ = await provider._check_data_source_health()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_min_fresh_ratio_zero_disables_guard(self):
        """min_fresh_ratio=0.0 reverts to legacy behaviour (ALL stale only)."""
        from services.trading.data_provider import (
            DataProviderConfig,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            config=DataProviderConfig(
                staleness_threshold_seconds=10.0,
                min_fresh_ratio=0.0,  # disable
            )
        )

        class _PartialSource:
            async def get_health_status(self):
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": 0.5,
                    "symbol_count": 40,
                    "fresh_symbol_count": 5,  # would fail under default
                    "stale_symbol_count": 35,
                }

        provider._data_source = _PartialSource()
        is_healthy, _ = await provider._check_data_source_health()
        # With guard disabled: only ALL-stale (fresh==0) triggers fail
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_zero_fresh_still_fails_under_legacy(self):
        """Hard failure (fresh=0) still fails even with guard disabled."""
        from services.trading.data_provider import (
            DataProviderConfig,
            MarketDataProvider,
        )

        provider = MarketDataProvider(
            config=DataProviderConfig(
                staleness_threshold_seconds=10.0,
                min_fresh_ratio=0.0,
            )
        )

        class _AllStaleSource:
            async def get_health_status(self):
                return {
                    "running": True,
                    "connected": True,
                    "staleness_seconds": 0.5,
                    "symbol_count": 40,
                    "fresh_symbol_count": 0,  # ALL stale
                    "stale_symbol_count": 40,
                }

        provider._data_source = _AllStaleSource()
        is_healthy, _ = await provider._check_data_source_health()
        assert is_healthy is False
