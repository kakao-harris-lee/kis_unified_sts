"""Tests for orchestrator metadata cache behavior and invalidation."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orchestrator(**kwargs):
    """Create a minimal TradingOrchestrator with mocked internals."""
    from services.trading.orchestrator import TradingConfig, TradingOrchestrator

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
    orch._daily_watchlist = {}
    orch._daily_indicators = {}
    orch._prev_day_volume_warned = False
    orch._universe_retention_seconds = 600
    orch._max_universe_size = 40
    orch._current_regime_confidence = None
    orch._macro_snapshot = None
    orch._macro_snapshot_monotonic = 0.0
    orch._macro_stream = "stream:macro.overnight"
    orch._scheduled_events = []
    orch._scheduled_events_monotonic = 0.0
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
            mock_redis.get.return_value = (
                '{"indicators": {"005930": {"atr": 2500, "prev_day_volume": 15000000}}}'
            )
            mock_redis_cls.get_client.return_value = mock_redis

            result = orch._refresh_daily_indicators()

            assert result is True
            assert orch._daily_indicators == redis_data["indicators"]

            # Cache should be updated with new daily indicators
            meta = orch._enriched_metadata_cache.get("005930", {})
            assert meta["atr"] == 2500
            assert meta["prev_day_volume"] == 15_000_000

    def test_dynamic_universe_filter_removes_symbols_without_daily_indicators(self):
        orch = _make_orchestrator()
        orch._daily_indicators = {"005930": {"atr": 1000.0}}

        codes, names, metadata = orch._filter_dynamic_universe_coverage(
            ["005930", "034020"],
            {"005930": "삼성전자", "034020": "두산에너빌리티"},
            {"005930": {"rank": 1}, "034020": {"rank": 2}},
        )

        assert codes == ["005930"]
        assert names == {"005930": "삼성전자"}
        assert metadata == {"005930": {"rank": 1}}

    def test_dynamic_universe_filter_is_configurable(self):
        orch = _make_orchestrator(require_daily_indicators_for_dynamic_universe=False)
        orch._daily_indicators = {"005930": {"atr": 1000.0}}

        codes, names, metadata = orch._filter_dynamic_universe_coverage(
            ["005930", "034020"],
            {"005930": "삼성전자", "034020": "두산에너빌리티"},
            {"005930": {"rank": 1}, "034020": {"rank": 2}},
        )

        assert codes == ["005930", "034020"]
        assert "034020" in names
        assert "034020" in metadata

    def test_dynamic_universe_filter_rejects_when_daily_indicators_missing(self):
        orch = _make_orchestrator()
        orch._daily_indicators = {}

        codes, names, metadata = orch._filter_dynamic_universe_coverage(
            ["005930"],
            {"005930": "삼성전자"},
            {"005930": {"rank": 1}},
        )

        assert codes == []
        assert names == {}
        assert metadata == {}

    def test_stable_universe_prunes_retained_symbols_without_daily_indicators(self):
        orch = _make_orchestrator()
        now = datetime.now()
        orch._daily_indicators = {"005930": {"atr": 1000.0}}
        orch._symbol_last_seen = {"005930": now, "034020": now}
        orch._symbol_metadata_cache = {
            "005930": {"rank": 1},
            "034020": {"rank": 2},
        }

        stable = orch._get_stable_universe()

        assert stable == {"005930"}
        assert "034020" not in orch._symbol_last_seen
        assert "034020" not in orch._symbol_metadata_cache

    def test_stable_universe_keeps_uncovered_position_symbols(self):
        orch = _make_orchestrator()
        now = datetime.now()
        orch._daily_indicators = {"005930": {"atr": 1000.0}}
        orch._symbol_last_seen = {"005930": now, "034020": now}
        pos = MagicMock()
        pos.code = "034020"
        orch._position_tracker = MagicMock()
        orch._position_tracker.positions = [pos]

        stable = orch._get_stable_universe()

        assert stable == {"005930", "034020"}

    def test_dip_candidates_not_merged_when_strategy_does_not_use_them(self):
        orch = _make_orchestrator()
        orch.config.symbols = ["005930"]
        orch._strategy_manager = MagicMock(strategy_names=["williams_r"])
        orch._dip_candidates = {"034020": {"name": "두산에너빌리티"}}

        changed = orch._merge_dip_candidates_into_universe()

        assert changed is False
        assert orch.config.symbols == ["005930"]
        assert "034020" not in orch._symbol_last_seen

    def test_dip_candidates_merge_for_active_bb_reversion(self):
        orch = _make_orchestrator()
        orch.config.symbols = ["005930"]
        orch._strategy_manager = MagicMock(strategy_names=["bb_reversion"])
        orch._dip_candidates = {"034020": {"name": "두산에너빌리티"}}

        changed = orch._merge_dip_candidates_into_universe()

        assert changed is True
        assert set(orch.config.symbols) == {"005930", "034020"}
        assert orch._symbol_metadata_cache["034020"]["source"] == "dip"

    def test_refresh_daily_indicators_loads_strategy_watchlist(self):
        orch = _make_orchestrator()

        with patch("shared.streaming.client.RedisClient") as mock_redis_cls:
            mock_redis = MagicMock()
            mock_redis.get.return_value = (
                '{"indicators":{"005930":{"daily_close":70000}},'
                '"strategies":{"daily_pullback":["005930"],"vr_composite":[]}}'
            )
            mock_redis_cls.get_client.return_value = mock_redis

            result = orch._refresh_daily_indicators()

        assert result is True
        assert orch._daily_watchlist["strategies"] == {
            "daily_pullback": ["005930"],
            "vr_composite": [],
        }
        assert orch._daily_watchlist["counts"] == {
            "daily_pullback": 1,
            "vr_composite": 0,
        }

    def test_dynamic_daily_watchlist_candidates_use_active_strategy_and_coverage(self):
        orch = _make_orchestrator()
        orch._strategy_manager = MagicMock(strategy_names=["daily_pullback"])
        orch._daily_indicators = {
            "005930": {"daily_close": 70000},
            "000660": {"daily_close": 120000},
        }
        orch._daily_watchlist = {
            "strategies": {
                "daily_pullback": ["005930", "034020"],
                "vr_composite": ["000660"],
            }
        }

        codes, names, metadata = orch._load_dynamic_daily_watchlist_candidates()

        assert codes == ["005930"]
        assert names == {"005930": ""}
        assert metadata == {
            "005930": {
                "source": "daily_watchlist",
                "daily_strategy_candidates": ["daily_pullback"],
            }
        }

    def test_dynamic_daily_watchlist_candidates_preserve_priority_metadata(self):
        orch = _make_orchestrator()
        orch._strategy_manager = MagicMock(strategy_names=["daily_pullback"])
        orch._daily_indicators = {"005930": {"daily_close": 70000}}
        orch._daily_watchlist = {
            "strategies": {"daily_pullback": ["005930"]},
            "metadata": {
                "005930": {
                    "trade_trend_priority": {
                        "score": 1.0,
                        "matched_sector": "semiconductor",
                    }
                }
            },
        }

        codes, names, metadata = orch._load_dynamic_daily_watchlist_candidates()

        assert codes == ["005930"]
        assert metadata["005930"]["source"] == "daily_watchlist"
        assert metadata["005930"]["trade_trend_priority"]["matched_sector"] == (
            "semiconductor"
        )

    def test_dynamic_daily_watchlist_candidates_can_be_disabled(self):
        orch = _make_orchestrator(include_daily_watchlist_in_dynamic_universe=False)
        orch._strategy_manager = MagicMock(strategy_names=["daily_pullback"])
        orch._daily_indicators = {"005930": {"daily_close": 70000}}
        orch._daily_watchlist = {"strategies": {"daily_pullback": ["005930"]}}

        codes, names, metadata = orch._load_dynamic_daily_watchlist_candidates()

        assert codes == []
        assert names == {}
        assert metadata == {}

    def test_merge_ranked_targets_preserves_order_and_merges_metadata(self):
        codes, names, metadata = _make_orchestrator()._merge_ranked_targets(
            ["005930", "000660"],
            {"005930": "삼성전자"},
            {"005930": {"source": "fusion"}},
            ["000660", "035420"],
            {"035420": "NAVER"},
            {"000660": {"source": "daily_watchlist"}},
        )

        assert codes == ["005930", "000660", "035420"]
        assert names == {"005930": "삼성전자", "035420": "NAVER"}
        assert metadata == {
            "005930": {"source": "fusion"},
            "000660": {"source": "daily_watchlist"},
        }

    def test_regime_universe_excludes_dip_position_only_and_missing_daily(self):
        orch = _make_orchestrator()
        now = datetime.now()
        orch.config.symbols = ["005930", "000660", "001740", "034020", "017900"]
        orch._daily_indicators = {
            "005930": {"daily_close": 70000},
            "000660": {"daily_close": 120000},
            "001740": {"daily_close": 5000},
            "034020": {"daily_close": 18000},
            "017900": {"daily_close": 2000},
        }
        orch._dip_candidates = {"017900": {"name": "광전자"}}
        orch._symbol_metadata_cache = {"034020": {"source": "dip"}}
        orch._symbol_last_seen = {
            "005930": now,
            "000660": now,
            "017900": now,
        }
        orch._position_tracker = SimpleNamespace(
            positions=[SimpleNamespace(code="001740")]
        )

        assert orch._get_regime_universe_symbols() == {"005930", "000660"}

    def test_classify_market_uses_filtered_regime_mfi_symbols(self):
        orch = _make_orchestrator()
        now = datetime.now()
        orch.config.symbols = ["005930", "000660", "001740", "017900"]
        orch._daily_indicators = {
            "005930": {"daily_close": 70000},
            "000660": {"daily_close": 120000},
            "001740": {"daily_close": 5000},
            "017900": {"daily_close": 2000},
        }
        orch._dip_candidates = {"017900": {"name": "광전자"}}
        orch._symbol_last_seen = {
            "005930": now,
            "000660": now,
            "017900": now,
        }
        orch._position_tracker = SimpleNamespace(
            positions=[SimpleNamespace(code="001740")]
        )
        engine = MagicMock()
        engine.get_market_mfi_values.return_value = {"005930": 83.0}
        orch._indicator_engine = engine

        regime = orch._classify_market(
            {
                "005930": {"change": 0.01},
                "000660": {"change": 0.01},
                "001740": {"change": -0.2},
                "017900": {"change": -0.2},
            }
        )

        assert regime == "BULL_STRONG"
        engine.get_market_mfi_values.assert_called_once_with({"005930", "000660"})

    def test_classify_market_does_not_fallback_to_mfi_missing_stock_symbols(self):
        orch = _make_orchestrator()
        now = datetime.now()
        orch.config.symbols = ["005930", "000660"]
        orch._daily_indicators = {
            "005930": {"daily_close": 70000},
            "000660": {"daily_close": 120000},
        }
        orch._symbol_last_seen = {"005930": now, "000660": now}
        engine = MagicMock()
        engine.get_market_mfi_values.return_value = {}
        orch._indicator_engine = engine

        regime = orch._classify_market(
            {"005930": {"change": 0.05}, "000660": {"change": 0.06}}
        )

        assert regime == "UNKNOWN"

    def test_classify_market_can_use_change_fallback_when_mfi_filter_disabled(self):
        orch = _make_orchestrator(regime_require_mfi_symbols=False)
        now = datetime.now()
        orch.config.symbols = ["005930", "000660"]
        orch._daily_indicators = {
            "005930": {"daily_close": 70000},
            "000660": {"daily_close": 120000},
        }
        orch._symbol_last_seen = {"005930": now, "000660": now}
        engine = MagicMock()
        engine.get_market_mfi_values.return_value = {}
        orch._indicator_engine = engine

        regime = orch._classify_market(
            {"005930": {"change": 0.05}, "000660": {"change": 0.06}}
        )

        assert regime == "BULL"

    def test_low_confidence_bear_regime_downgrades_to_sideways_down(self):
        orch = _make_orchestrator()
        symbols = [f"{idx:06d}" for idx in range(20)]
        orch.config.symbols = symbols
        orch._daily_indicators = {code: {"daily_close": 100.0} for code in symbols}
        engine = MagicMock()
        engine.get_market_mfi_values.return_value = {
            "000000": 30.0,
            "000001": 32.0,
            "000002": 33.0,
        }
        orch._indicator_engine = engine

        regime = orch._classify_market({code: {"change": -0.05} for code in symbols})

        assert regime == "SIDEWAYS_DOWN"
        assert orch._last_regime_diagnostics["raw_regime"] == "BEAR_STRONG"
        assert orch._last_regime_diagnostics["effective_regime"] == "SIDEWAYS_DOWN"
        assert "mfi_symbols<8" in orch._last_regime_diagnostics["low_confidence_reason"]

    def test_confident_bear_regime_still_blocks(self):
        orch = _make_orchestrator()
        symbols = [f"{idx:06d}" for idx in range(10)]
        orch.config.symbols = symbols
        orch._daily_indicators = {code: {"daily_close": 100.0} for code in symbols}
        engine = MagicMock()
        engine.get_market_mfi_values.return_value = {code: 30.0 for code in symbols[:8]}
        orch._indicator_engine = engine

        regime = orch._classify_market({code: {"change": -0.05} for code in symbols})

        assert regime == "BEAR_STRONG"
        assert orch._last_regime_diagnostics["raw_regime"] == "BEAR_STRONG"
        assert orch._last_regime_diagnostics["effective_regime"] == "BEAR_STRONG"
        assert orch._last_regime_diagnostics["low_confidence_reason"] is None

    def test_get_stable_universe_protects_daily_watchlist_candidates_over_cold(self):
        orch = _make_orchestrator()
        orch._max_universe_size = 2
        now = datetime.now()
        orch._symbol_last_seen = {
            "005930": now,
            "000660": now,
            "035420": now,
        }
        orch._symbol_metadata_cache = {
            "035420": {
                "source": "daily_watchlist",
                "daily_strategy_candidates": ["daily_pullback"],
            }
        }

        stable = orch._get_stable_universe()

        assert "035420" in stable
        assert len(stable) == 2

    def test_daily_watchlist_candidate_can_bypass_intraday_warmup(self):
        orch = _make_orchestrator()
        orch._strategy_manager = MagicMock(
            strategy_names=["daily_pullback", "vr_composite"]
        )
        orch._cached_daily_indicators = {"005930": {"daily_close": 70000}}
        orch._daily_watchlist = {
            "strategies": {
                "daily_pullback": ["005930"],
                "vr_composite": [],
            }
        }
        orch._symbol_metadata_cache = {
            "005930": {
                "source": "daily_watchlist",
                "daily_strategy_candidates": ["daily_pullback"],
            }
        }

        assert orch._can_bypass_entry_warmup_for_daily_watchlist("005930") is True

    def test_daily_watchlist_warmup_bypass_requires_all_active_strategies_daily(self):
        orch = _make_orchestrator()
        orch._strategy_manager = MagicMock(
            strategy_names=["daily_pullback", "opening_volume_surge"]
        )
        orch._cached_daily_indicators = {"005930": {"daily_close": 70000}}
        orch._daily_watchlist = {"strategies": {"daily_pullback": ["005930"]}}
        orch._symbol_metadata_cache = {
            "005930": {"daily_strategy_candidates": ["daily_pullback"]}
        }

        assert orch._can_bypass_entry_warmup_for_daily_watchlist("005930") is False

    def test_daily_watchlist_warmup_bypass_is_configurable(self):
        orch = _make_orchestrator(
            allow_daily_watchlist_entry_before_intraday_warmup=False
        )
        orch._strategy_manager = MagicMock(strategy_names=["daily_pullback"])
        orch._cached_daily_indicators = {"005930": {"daily_close": 70000}}
        orch._daily_watchlist = {"strategies": {"daily_pullback": ["005930"]}}
        orch._symbol_metadata_cache = {
            "005930": {"daily_strategy_candidates": ["daily_pullback"]}
        }

        assert orch._can_bypass_entry_warmup_for_daily_watchlist("005930") is False

    @pytest.mark.asyncio
    async def test_handle_entries_checks_daily_candidate_before_intraday_warmup(self):
        orch = _make_orchestrator()
        signal = MagicMock()
        orch._metrics = MagicMock()
        orch._data_provider = MagicMock()
        orch._position_tracker = MagicMock(
            positions=[],
            can_open_position=MagicMock(return_value=True),
        )
        orch._strategy_manager = MagicMock(
            strategy_names=["daily_pullback"],
            check_entries=AsyncMock(return_value=[signal]),
        )
        orch._indicator_engine = MagicMock(is_warm=MagicMock(return_value=False))
        orch._indicator_resolver = MagicMock(
            collect_entry_indicators=MagicMock(return_value={})
        )
        orch._cached_daily_indicators = {"005930": {"daily_close": 70000}}
        orch._daily_watchlist = {"strategies": {"daily_pullback": ["005930"]}}
        orch._symbol_metadata_cache = {
            "005930": {"daily_strategy_candidates": ["daily_pullback"]}
        }
        orch._enriched_metadata_cache = {
            "005930": {"daily_close": 70000, "code": "005930"}
        }
        orch._get_market_data_snapshot = AsyncMock(
            return_value={"005930": {"code": "005930", "close": 70100}}
        )
        orch._filter_reentry_guarded_signals = lambda signals: signals
        orch._execute_entry = AsyncMock()

        signals = await orch._handle_entry()

        assert signals == [signal]
        orch._strategy_manager.check_entries.assert_awaited_once()
        context = orch._strategy_manager.check_entries.await_args.args[0]
        assert context.market_data["close"] == 70100
        assert context.indicators["daily_close"] == 70000
        orch._execute_entry.assert_awaited_once_with(signal)

    def test_entry_signal_priority_uses_explicit_priority_then_confidence(self):
        orch = _make_orchestrator()
        low = MagicMock(
            code="000001",
            strategy="daily_pullback",
            confidence=0.95,
            metadata={"entry_priority": 2},
        )
        high = MagicMock(
            code="000002",
            strategy="daily_pullback",
            confidence=0.70,
            metadata={"entry_priority": 1},
        )
        same_priority_better_confidence = MagicMock(
            code="000003",
            strategy="daily_pullback",
            confidence=0.90,
            metadata={"entry_priority": 1},
        )

        ordered = orch._prioritize_entry_signals(
            [low, high, same_priority_better_confidence]
        )

        assert ordered == [same_priority_better_confidence, high, low]

    @pytest.mark.asyncio
    async def test_handle_entry_executes_stock_signals_by_priority_order(self):
        orch = _make_orchestrator()
        low = MagicMock(
            code="000001",
            strategy="daily_pullback",
            confidence=0.40,
            metadata={},
        )
        high = MagicMock(
            code="000002",
            strategy="daily_pullback",
            confidence=0.90,
            metadata={},
        )
        orch._metrics = MagicMock()
        orch._data_provider = MagicMock()
        orch._position_tracker = MagicMock(
            positions=[],
            can_open_position=MagicMock(return_value=True),
        )

        async def check_entries(context):
            if context.market_data["code"] == "000001":
                return [low]
            return [high]

        orch._strategy_manager = MagicMock(
            strategy_names=["daily_pullback"],
            check_entries=AsyncMock(side_effect=check_entries),
        )
        orch._indicator_engine = None
        orch._cached_daily_indicators = {}
        orch._daily_watchlist = {}
        orch._symbol_metadata_cache = {}
        orch._enriched_metadata_cache = {}
        orch._get_market_data_snapshot = AsyncMock(
            return_value={
                "000001": {"code": "000001", "close": 1000},
                "000002": {"code": "000002", "close": 2000},
            }
        )
        orch._filter_reentry_guarded_signals = lambda signals: signals
        orch._execute_entry = AsyncMock()

        signals = await orch._handle_entry()

        assert signals == [high, low]
        assert [call.args[0] for call in orch._execute_entry.await_args_list] == [
            high,
            low,
        ]


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
            code
            for code, last_seen in orch._symbol_last_seen.items()
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
            code
            for code, last_seen in orch._symbol_last_seen.items()
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
        context = (
            call_args.args[0] if call_args.args else call_args.kwargs.get("context")
        )
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
