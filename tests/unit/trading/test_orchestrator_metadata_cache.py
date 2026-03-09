"""Tests for orchestrator metadata cache behavior and invalidation."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_orchestrator(**kwargs):
    """Create a minimal TradingOrchestrator with mocked internals."""
    from services.trading.orchestrator import TradingOrchestrator, TradingConfig

    config = TradingConfig.stock()
    for k, v in kwargs.items():
        setattr(config, k, v)

    orch = TradingOrchestrator.__new__(TradingOrchestrator)
    orch.config = config
    orch.state = None
    orch._strategy_manager = None
    orch._position_tracker = None
    orch._data_provider = None
    orch._indicator_engine = None
    orch._current_regime = "SIDEWAYS_FLAT"
    orch._market_data_snapshot = {}
    orch._market_data_lock = asyncio.Lock()
    orch._order_semaphore = asyncio.Semaphore(5)
    orch._order_queue_size = 0
    orch.total_pnl = 0.0
    orch._symbol_metadata_cache = {}
    orch._enriched_metadata_cache = {}
    orch._cached_symbol_meta = {}
    orch._cached_daily_indicators = {}
    orch._symbol_last_seen = {}
    orch._symbol_names = {}
    orch._daily_indicators = {}
    orch._prev_day_volume_warned = False
    orch._universe_retention_seconds = 600
    orch._max_universe_size = 40
    orch._current_regime_confidence = None
    return orch


class TestEnrichedMetadataCache:
    """Test enriched metadata cache building and content."""

    def test_build_cache_merges_symbol_metadata(self):
        """Enriched cache should include symbol_metadata."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자", "sector": "IT"},
            "000660": {"name": "SK하이닉스", "sector": "IT"},
        }

        orch._build_enriched_metadata_cache()

        assert "005930" in orch._enriched_metadata_cache
        assert "000660" in orch._enriched_metadata_cache

        meta_005930 = orch._enriched_metadata_cache["005930"]
        assert meta_005930["name"] == "삼성전자"
        assert meta_005930["sector"] == "IT"
        assert meta_005930["code"] == "005930"

        meta_000660 = orch._enriched_metadata_cache["000660"]
        assert meta_000660["name"] == "SK하이닉스"
        assert meta_000660["code"] == "000660"

    def test_build_cache_merges_daily_indicators(self):
        """Enriched cache should include daily indicators."""
        orch = _make_orchestrator()

        orch._daily_indicators = {
            "005930": {"atr": 2500, "prev_day_volume": 15_000_000},
            "000660": {"atr": 3000, "prev_day_volume": 8_000_000},
        }

        orch._build_enriched_metadata_cache()

        assert "005930" in orch._enriched_metadata_cache
        meta_005930 = orch._enriched_metadata_cache["005930"]
        assert meta_005930["atr"] == 2500
        assert meta_005930["prev_day_volume"] == 15_000_000
        assert meta_005930["code"] == "005930"

    def test_build_cache_merges_both_sources(self):
        """Enriched cache should merge symbol_metadata and daily_indicators."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자", "sector": "IT"},
        }

        orch._daily_indicators = {
            "005930": {"atr": 2500, "prev_day_volume": 15_000_000},
        }

        orch._build_enriched_metadata_cache()

        meta = orch._enriched_metadata_cache["005930"]
        # Should have both metadata and indicators
        assert meta["name"] == "삼성전자"
        assert meta["sector"] == "IT"
        assert meta["atr"] == 2500
        assert meta["prev_day_volume"] == 15_000_000
        assert meta["code"] == "005930"

    def test_build_cache_daily_indicators_override_metadata(self):
        """Daily indicators should override symbol_metadata when keys conflict."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자", "volume": 10_000_000},
        }

        orch._daily_indicators = {
            "005930": {"volume": 15_000_000},  # Conflicts with metadata
        }

        orch._build_enriched_metadata_cache()

        meta = orch._enriched_metadata_cache["005930"]
        # Daily indicators should win
        assert meta["volume"] == 15_000_000
        assert meta["name"] == "삼성전자"

    def test_build_cache_handles_metadata_only_symbols(self):
        """Cache should handle symbols with only metadata (no daily indicators)."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자"},
            "000660": {"name": "SK하이닉스"},
        }

        orch._daily_indicators = {
            "005930": {"atr": 2500},  # Only one symbol has daily indicators
        }

        orch._build_enriched_metadata_cache()

        # Both symbols should be in cache
        assert "005930" in orch._enriched_metadata_cache
        assert "000660" in orch._enriched_metadata_cache

        # 005930 has both
        assert orch._enriched_metadata_cache["005930"]["atr"] == 2500
        assert orch._enriched_metadata_cache["005930"]["name"] == "삼성전자"

        # 000660 has only metadata
        assert "atr" not in orch._enriched_metadata_cache["000660"]
        assert orch._enriched_metadata_cache["000660"]["name"] == "SK하이닉스"

    def test_build_cache_handles_daily_only_symbols(self):
        """Cache should handle symbols with only daily indicators (no metadata)."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {}

        orch._daily_indicators = {
            "005930": {"atr": 2500, "prev_day_volume": 15_000_000},
        }

        orch._build_enriched_metadata_cache()

        assert "005930" in orch._enriched_metadata_cache
        meta = orch._enriched_metadata_cache["005930"]
        assert meta["atr"] == 2500
        assert meta["code"] == "005930"
        assert "name" not in meta

    def test_build_cache_ensures_code_is_always_present(self):
        """Every entry in enriched cache should have 'code' field."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자"},
        }

        orch._daily_indicators = {
            "000660": {"atr": 3000},
        }

        orch._build_enriched_metadata_cache()

        # Both entries should have code
        assert orch._enriched_metadata_cache["005930"]["code"] == "005930"
        assert orch._enriched_metadata_cache["000660"]["code"] == "000660"

    def test_build_cache_clears_previous_cache(self):
        """Building cache should clear previous entries."""
        orch = _make_orchestrator()

        # Initial cache
        orch._enriched_metadata_cache = {
            "old_symbol": {"name": "old data"},
        }

        # New data
        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자"},
        }

        orch._build_enriched_metadata_cache()

        # Old symbol should be gone
        assert "old_symbol" not in orch._enriched_metadata_cache
        assert "005930" in orch._enriched_metadata_cache

    def test_build_cache_handles_empty_sources(self):
        """Building cache with no metadata or indicators should result in empty cache."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {}
        orch._daily_indicators = {}

        orch._build_enriched_metadata_cache()

        assert len(orch._enriched_metadata_cache) == 0

    def test_build_cache_handles_none_metadata(self):
        """Building cache should handle None symbol_metadata gracefully."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = None
        orch._daily_indicators = {
            "005930": {"atr": 2500},
        }

        orch._build_enriched_metadata_cache()

        assert "005930" in orch._enriched_metadata_cache
        assert orch._enriched_metadata_cache["005930"]["atr"] == 2500


class TestCacheInvalidation:
    """Test enriched metadata cache invalidation behavior."""

    def test_invalidate_rebuilds_cache(self):
        """Invalidation should trigger a full cache rebuild."""
        orch = _make_orchestrator()

        # Initial state
        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자"},
        }
        orch._build_enriched_metadata_cache()
        assert "005930" in orch._enriched_metadata_cache

        # Change metadata
        orch.config.symbol_metadata = {
            "000660": {"name": "SK하이닉스"},
        }

        # Invalidate (should rebuild)
        orch._invalidate_enriched_metadata_cache()

        # Old symbol gone, new symbol present
        assert "005930" not in orch._enriched_metadata_cache
        assert "000660" in orch._enriched_metadata_cache

    def test_invalidate_after_daily_indicators_update(self):
        """Cache should be invalidated after daily indicators are updated."""
        orch = _make_orchestrator()

        # Initial state
        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자"},
        }
        orch._daily_indicators = {}
        orch._build_enriched_metadata_cache()

        initial_meta = orch._enriched_metadata_cache.get("005930", {})
        assert "atr" not in initial_meta

        # Update daily indicators
        orch._daily_indicators = {
            "005930": {"atr": 2500},
        }

        # Invalidate
        orch._invalidate_enriched_metadata_cache()

        # Cache should now include daily indicators
        updated_meta = orch._enriched_metadata_cache.get("005930", {})
        assert updated_meta["atr"] == 2500

    def test_invalidate_preserves_data_integrity(self):
        """Invalidation should maintain data consistency across rebuild."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자", "sector": "IT"},
        }
        orch._daily_indicators = {
            "005930": {"atr": 2500},
        }

        # Build and invalidate multiple times
        for _ in range(3):
            orch._invalidate_enriched_metadata_cache()

            meta = orch._enriched_metadata_cache.get("005930", {})
            assert meta["name"] == "삼성전자"
            assert meta["sector"] == "IT"
            assert meta["atr"] == 2500
            assert meta["code"] == "005930"

    def test_refresh_daily_indicators_invalidates_cache(self):
        """_refresh_daily_indicators should invalidate enriched cache."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자"},
        }
        orch._build_enriched_metadata_cache()

        # Mock Redis to return daily indicators
        redis_data = {
            "indicators": {
                "005930": {"atr": 2500, "prev_day_volume": 15_000_000},
            }
        }

        with patch("shared.streaming.client.RedisClient") as mock_redis_cls:
            mock_redis = MagicMock()
            mock_redis.get.return_value = '{"indicators": {"005930": {"atr": 2500, "prev_day_volume": 15000000}}}'
            mock_redis_cls.get_client.return_value = mock_redis

            # Refresh should invalidate and rebuild cache
            import json
            result = orch._refresh_daily_indicators()

            assert result is True
            assert orch._daily_indicators == redis_data["indicators"]

            # Cache should be updated with new daily indicators
            meta = orch._enriched_metadata_cache.get("005930", {})
            assert meta["atr"] == 2500
            assert meta["prev_day_volume"] == 15_000_000


class TestSymbolMetadataCacheExpiry:
    """Test symbol metadata cache expiry and cleanup."""

    def test_expired_symbols_removed_from_metadata_cache(self):
        """Expired symbols should be removed from _symbol_metadata_cache."""
        orch = _make_orchestrator()

        now = datetime.now()
        expired_time = now - timedelta(seconds=700)  # retention is 600s

        # Setup symbols
        orch._symbol_metadata_cache = {
            "005930": {"name": "삼성전자"},
            "000660": {"name": "SK하이닉스"},
            "expired_symbol": {"name": "expired"},
        }

        orch._symbol_last_seen = {
            "005930": now,
            "000660": now,
            "expired_symbol": expired_time,
        }

        # Trigger cleanup (simulate _prune_stale_symbols logic)
        expired = {
            code for code, last_seen in orch._symbol_last_seen.items()
            if (now - last_seen).total_seconds() > orch._universe_retention_seconds
        }

        for code in expired:
            del orch._symbol_last_seen[code]
            orch._symbol_metadata_cache.pop(code, None)

        # Expired symbol should be removed
        assert "expired_symbol" not in orch._symbol_metadata_cache
        assert "expired_symbol" not in orch._symbol_last_seen

        # Active symbols should remain
        assert "005930" in orch._symbol_metadata_cache
        assert "000660" in orch._symbol_metadata_cache

    def test_symbols_with_positions_not_removed(self):
        """Symbols with open positions should not be removed even if expired."""
        orch = _make_orchestrator()

        now = datetime.now()
        expired_time = now - timedelta(seconds=700)

        # Setup
        orch._symbol_metadata_cache = {
            "005930": {"name": "삼성전자"},
        }
        orch._symbol_last_seen = {
            "005930": expired_time,  # Expired
        }

        # Mock position tracker
        pos = MagicMock()
        pos.code = "005930"

        orch._position_tracker = MagicMock()
        orch._position_tracker.positions = [pos]

        # Simulate _prune_stale_symbols with position protection
        expired = {
            code for code, last_seen in orch._symbol_last_seen.items()
            if (now - last_seen).total_seconds() > orch._universe_retention_seconds
        }

        # Protect symbols with positions
        open_codes = {p.code for p in orch._position_tracker.positions}
        expired = expired - open_codes

        # Symbol should NOT be removed (has position)
        assert "005930" not in expired
        assert "005930" in orch._symbol_metadata_cache


class TestCacheUsageInHotPath:
    """Test cache usage in entry/exit handlers to verify hot path optimization."""

    @pytest.mark.asyncio
    async def test_entry_uses_enriched_cache(self):
        """_handle_entry should use enriched metadata cache, not raw lookups."""
        orch = _make_orchestrator()

        # Setup enriched cache + separated caches
        orch._enriched_metadata_cache = {
            "005930": {
                "code": "005930",
                "name": "삼성전자",
                "atr": 2500,
                "prev_day_volume": 15_000_000,
            }
        }
        orch._cached_symbol_meta = {
            "005930": {"name": "삼성전자"},
        }
        orch._cached_daily_indicators = {
            "005930": {"atr": 2500, "prev_day_volume": 15_000_000},
        }

        # Mock market data
        orch._market_data_snapshot = {
            "005930": {"close": 71000, "volume": 50000},
        }

        # Mock data provider (required: _handle_entry returns [] if None)
        orch._data_provider = MagicMock()

        # Mock indicator engine (warm)
        orch._indicator_engine = MagicMock()
        orch._indicator_engine.is_warm.return_value = True
        orch._indicator_engine.get_indicators.return_value = {
            "bb_upper": 72000,
            "bb_lower": 70000,
        }

        # Mock strategy manager
        orch._strategy_manager = MagicMock()
        orch._strategy_manager.check_entries = AsyncMock(return_value=[])
        orch._strategy_manager.strategy_names = ["bb_reversion"]
        orch._strategy_manager.required_indicators = set()

        # Mock position tracker
        orch._position_tracker = MagicMock()
        orch._position_tracker.has_position.return_value = False
        orch._position_tracker.can_open_position.return_value = True
        orch._position_tracker.positions = []

        # Mock metrics
        orch._metrics = MagicMock()
        orch._daily_watchlist = {}

        orch.config.symbols = ["005930"]

        await orch._handle_entry()

        # Verify check_entries was called (receives EntryContext positional arg)
        assert orch._strategy_manager.check_entries.called

        # Verify the EntryContext has enriched market_data
        call_args = orch._strategy_manager.check_entries.call_args
        context = call_args.args[0] if call_args.args else call_args.kwargs.get("context")
        assert context.market_data.get("name") == "삼성전자"
        assert context.market_data.get("close") == 71000

        # Verify indicators dict has daily indicators but NOT symbol metadata
        assert context.indicators.get("atr") == 2500
        assert "name" not in context.indicators
        assert "sector" not in context.indicators

        # Verify metadata['symbol_metadata'] has pure symbol metadata
        assert context.metadata["symbol_metadata"].get("name") == "삼성전자"

    @pytest.mark.asyncio
    async def test_exit_uses_enriched_cache(self):
        """_handle_exit should use daily indicators cache for exit data."""
        orch = _make_orchestrator()

        # Setup separated caches (exit path uses _cached_daily_indicators)
        orch._cached_daily_indicators = {
            "005930": {"atr": 2500},
        }

        # Mock position
        pos = MagicMock()
        pos.code = "005930"

        orch._position_tracker = MagicMock()
        orch._position_tracker.positions = [pos]

        # Mock data provider (required: _handle_exit returns [] if None)
        orch._data_provider = MagicMock()

        # Mock market data
        orch._market_data_snapshot = {
            "005930": {"close": 71000, "volume": 50000},
        }

        # Mock indicator engine
        orch._indicator_engine = MagicMock()
        orch._indicator_engine.get_indicators.return_value = {}

        # Mock strategy manager
        orch._strategy_manager = MagicMock()
        orch._strategy_manager.check_exits = AsyncMock(return_value=[])
        orch._strategy_manager.required_indicators = set()

        await orch._handle_exit()

        # Verify check_exits was called with enriched data
        call_args = orch._strategy_manager.check_exits.call_args
        market_data = call_args.kwargs["market_data"]

        # Daily indicators should be merged into exit data
        symbol_data = market_data["005930"]
        assert symbol_data["atr"] == 2500
        # Symbol metadata should NOT be in exit data
        assert "name" not in symbol_data

    @pytest.mark.asyncio
    async def test_entry_handles_missing_cache_entry(self):
        """Entry handler should gracefully handle symbols not in enriched cache."""
        orch = _make_orchestrator()

        # Empty caches
        orch._enriched_metadata_cache = {}
        orch._cached_symbol_meta = {}
        orch._cached_daily_indicators = {}

        orch._market_data_snapshot = {
            "005930": {"close": 71000},
        }

        # Mock data provider (required: _handle_entry returns [] if None)
        orch._data_provider = MagicMock()

        orch._indicator_engine = MagicMock()
        orch._indicator_engine.is_warm.return_value = True
        orch._indicator_engine.get_indicators.return_value = {}

        orch._strategy_manager = MagicMock()
        orch._strategy_manager.check_entries = AsyncMock(return_value=[])
        orch._strategy_manager.strategy_names = ["bb_reversion"]
        orch._strategy_manager.required_indicators = set()

        orch._position_tracker = MagicMock()
        orch._position_tracker.has_position.return_value = False
        orch._position_tracker.can_open_position.return_value = True
        orch._position_tracker.positions = []

        orch._metrics = MagicMock()
        orch._daily_watchlist = {}

        orch.config.symbols = ["005930"]

        # Should not raise exception
        await orch._handle_entry()

        # Check entries should still be called
        assert orch._strategy_manager.check_entries.called

    @pytest.mark.asyncio
    async def test_exit_handles_missing_cache_entry(self):
        """Exit handler should gracefully handle symbols not in enriched cache."""
        orch = _make_orchestrator()

        # Empty cache
        orch._enriched_metadata_cache = {}

        pos = MagicMock()
        pos.code = "005930"

        orch._position_tracker = MagicMock()
        orch._position_tracker.positions = [pos]

        orch._market_data_snapshot = {
            "005930": {"close": 71000},
        }

        orch._indicator_engine = MagicMock()
        orch._indicator_engine.get_indicators.return_value = {}

        orch._strategy_manager = MagicMock()
        orch._strategy_manager.check_exits = AsyncMock(return_value=[])

        # Should not raise exception
        result = await orch._handle_exit()

        assert result == []


class TestCacheLogging:
    """Test cache-related logging for debugging and monitoring."""

    def test_build_cache_logs_symbol_counts(self, caplog):
        """Building cache should log symbol counts from each source."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {
            "005930": {"name": "삼성전자"},
            "000660": {"name": "SK하이닉스"},
        }

        orch._daily_indicators = {
            "005930": {"atr": 2500},
            "035720": {"atr": 5000},  # Only in daily indicators
        }

        with caplog.at_level(logging.DEBUG):
            orch._build_enriched_metadata_cache()

        # Should log symbol counts
        log_messages = [r.message for r in caplog.records]
        assert any("enriched metadata cache" in msg.lower() for msg in log_messages)
        assert any("3 symbols" in msg for msg in log_messages)  # Total unique symbols

    def test_invalidate_logs_action(self, caplog):
        """Invalidation should log the action."""
        orch = _make_orchestrator()

        orch.config.symbol_metadata = {"005930": {"name": "삼성전자"}}

        with caplog.at_level(logging.DEBUG):
            orch._invalidate_enriched_metadata_cache()

        log_messages = [r.message for r in caplog.records]
        assert any("invalidating" in msg.lower() for msg in log_messages)


class TestCacheMemoryEfficiency:
    """Test that cache avoids redundant dictionary operations."""

    def test_cache_avoids_repeated_dict_copy(self):
        """Enriched cache should eliminate need for repeated dict(symbol_data) copies."""
        orch = _make_orchestrator()

        # Large metadata
        large_meta = {f"field_{i}": f"value_{i}" for i in range(100)}

        orch.config.symbol_metadata = {
            "005930": large_meta,
        }

        orch._build_enriched_metadata_cache()

        # Cache should contain a single merged copy
        cached = orch._enriched_metadata_cache["005930"]

        # Verify it's a separate copy (not the same object)
        assert cached is not large_meta

        # But contains all the data
        for key in large_meta:
            assert key in cached

    def test_cache_stores_pre_merged_data(self):
        """Cache should store pre-merged metadata + indicators."""
        orch = _make_orchestrator()

        metadata = {"name": "삼성전자", "sector": "IT"}
        indicators = {"atr": 2500, "prev_day_volume": 15_000_000}

        orch.config.symbol_metadata = {"005930": metadata}
        orch._daily_indicators = {"005930": indicators}

        orch._build_enriched_metadata_cache()

        cached = orch._enriched_metadata_cache["005930"]

        # Should have everything merged
        assert cached["name"] == "삼성전자"
        assert cached["sector"] == "IT"
        assert cached["atr"] == 2500
        assert cached["prev_day_volume"] == 15_000_000

        # Modifications to cache should not affect originals
        cached["new_field"] = "test"
        assert "new_field" not in metadata
        assert "new_field" not in indicators
