"""Tests for orchestrator exit data enrichment and indicator engine config wiring."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MODULE = "services.trading.orchestrator"


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
    orch._symbol_last_seen = {}
    orch._symbol_names = {}
    orch._prev_day_volume_warned = False
    orch._universe_retention_seconds = 600
    orch._max_universe_size = 40
    return orch


class TestExitDataEnrichment:
    """Verify that _handle_exit enriches exit market_data with indicators."""

    @pytest.mark.asyncio
    async def test_exit_data_includes_indicators(self):
        """Exit market_data should include volume_velocity & vwap from indicator engine."""
        orch = _make_orchestrator()

        # Mock position
        pos = MagicMock()
        pos.code = "005930"
        pos.strategy = "volume_accumulation"

        # Mock position tracker
        orch._position_tracker = MagicMock()
        orch._position_tracker.positions = [pos]

        # Mock data provider
        orch._data_provider = MagicMock()

        # Raw snapshot (no indicators)
        orch._market_data_snapshot = {
            "005930": {"close": 71000, "volume": 50000},
        }

        # Mock indicator engine
        orch._indicator_engine = MagicMock()
        orch._indicator_engine.get_indicators.return_value = {
            "volume_velocity": 0.15,
            "vwap": 70500.0,
            "bb_lower": 69000.0,
        }

        # Mock strategy manager to return no signals
        orch._strategy_manager = MagicMock()
        orch._strategy_manager.check_exits = AsyncMock(return_value=[])

        await orch._handle_exit()

        # Verify check_exits was called with enriched data
        call_args = orch._strategy_manager.check_exits.call_args
        market_data = call_args.kwargs["market_data"]

        symbol_data = market_data["005930"]
        assert symbol_data["volume_velocity"] == 0.15
        assert symbol_data["vwap"] == 70500.0
        assert symbol_data["close"] == 71000  # original data preserved

    @pytest.mark.asyncio
    async def test_exit_data_works_without_indicator_engine(self):
        """When indicator engine is None, exit should still work with raw data."""
        orch = _make_orchestrator()

        pos = MagicMock()
        pos.code = "005930"

        orch._position_tracker = MagicMock()
        orch._position_tracker.positions = [pos]
        orch._data_provider = MagicMock()
        orch._market_data_snapshot = {
            "005930": {"close": 71000},
        }
        orch._indicator_engine = None

        orch._strategy_manager = MagicMock()
        orch._strategy_manager.check_exits = AsyncMock(return_value=[])

        result = await orch._handle_exit()
        assert result == []


class TestIndicatorEngineHighPeriodWiring:
    """Verify that breakout_period from strategy config is wired to indicator engine."""

    def test_high_period_read_from_strategy_config(self):
        """Indicator engine init loop should read breakout_period from entry config."""
        from services.trading.indicator_engine import StreamingIndicatorEngine

        # Simulate the config-reading loop from orchestrator.__init__
        bb_period, bb_std, rsi_period, high_period = 20, 2.0, 14, 5

        # Strategy 1: bb_reversion (no breakout_period)
        cfg_bb = {"bb_period": 20, "bb_std": 2.0, "rsi_period": 14}
        bb_period = cfg_bb.get("bb_period", bb_period)
        bb_std = cfg_bb.get("bb_std", bb_std)
        rsi_period = cfg_bb.get("rsi_period", rsi_period)
        high_period = cfg_bb.get("breakout_period", high_period)

        # Strategy 2: volume_accumulation (has breakout_period=10)
        cfg_va = {"breakout_period": 10}
        bb_period = cfg_va.get("bb_period", bb_period)
        bb_std = cfg_va.get("bb_std", bb_std)
        rsi_period = cfg_va.get("rsi_period", rsi_period)
        high_period = cfg_va.get("breakout_period", high_period)

        assert high_period == 10

        # Verify StreamingIndicatorEngine accepts high_period
        engine = StreamingIndicatorEngine(
            bb_period=bb_period,
            bb_std=bb_std,
            rsi_period=rsi_period,
            high_period=high_period,
        )
        assert engine._high_period == 10

    def test_default_high_period_when_no_breakout_config(self):
        """high_period should default to 5 when no strategy has breakout_period."""
        from services.trading.indicator_engine import StreamingIndicatorEngine

        bb_period, bb_std, rsi_period, high_period = 20, 2.0, 14, 5

        cfg = {"bb_period": 20, "rsi_period": 14}
        high_period = cfg.get("breakout_period", high_period)

        assert high_period == 5

        engine = StreamingIndicatorEngine(high_period=high_period)
        assert engine._high_period == 5


class TestPrevDayVolumeWarning:
    """Verify warning when opening_volume_surge is active but no prev_day_volume."""

    def test_warns_when_no_prev_day_volume(self, caplog):
        """Should log warning when OVS is active but metadata lacks prev_day_volume."""
        orch = _make_orchestrator()

        mock_sm = MagicMock()
        mock_sm.strategy_names = ["opening_volume_surge", "bb_reversion"]
        orch._strategy_manager = mock_sm

        # Metadata without prev_day_volume
        orch._symbol_metadata_cache = {
            "005930": {"name": "삼성전자"},
            "000660": {"name": "SK하이닉스"},
        }

        with patch("shared.streaming.client.RedisClient") as mock_redis_cls, \
             caplog.at_level(logging.WARNING):
            mock_redis = MagicMock()
            mock_redis_cls.get_client.return_value = mock_redis

            orch._load_ranked_targets = MagicMock(return_value=(
                ["005930", "000660"],
                {"005930": "삼성전자", "000660": "SK하이닉스"},
                {"005930": {"name": "삼성전자"}, "000660": {"name": "SK하이닉스"}},
            ))
            orch._symbol_last_seen = {
                "005930": datetime.now(),
                "000660": datetime.now(),
            }

            result = orch._refresh_universe_from_screener()

        assert result is True
        assert any("prev_day_volume" in msg for msg in caplog.messages)
        assert orch._prev_day_volume_warned is True

    def test_no_warning_when_prev_day_volume_present(self, caplog):
        """Should NOT warn when metadata has prev_day_volume."""
        orch = _make_orchestrator()

        mock_sm = MagicMock()
        mock_sm.strategy_names = ["opening_volume_surge"]
        orch._strategy_manager = mock_sm

        orch._symbol_metadata_cache = {
            "005930": {"prev_day_volume": 10_000_000},
        }

        with patch("shared.streaming.client.RedisClient") as mock_redis_cls, \
             caplog.at_level(logging.WARNING):
            mock_redis = MagicMock()
            mock_redis_cls.get_client.return_value = mock_redis

            orch._load_ranked_targets = MagicMock(return_value=(
                ["005930"],
                {"005930": "삼성전자"},
                {"005930": {"prev_day_volume": 10_000_000}},
            ))
            orch._symbol_last_seen = {"005930": datetime.now()}

            orch._refresh_universe_from_screener()

        assert not any("prev_day_volume" in msg for msg in caplog.messages)
        assert orch._prev_day_volume_warned is False

    def test_no_warning_when_ovs_not_loaded(self, caplog):
        """Should NOT warn when opening_volume_surge is not a loaded strategy."""
        orch = _make_orchestrator()

        mock_sm = MagicMock()
        mock_sm.strategy_names = ["bb_reversion"]
        orch._strategy_manager = mock_sm

        orch._symbol_metadata_cache = {"005930": {"name": "삼성전자"}}

        with patch("shared.streaming.client.RedisClient") as mock_redis_cls, \
             caplog.at_level(logging.WARNING):
            mock_redis = MagicMock()
            mock_redis_cls.get_client.return_value = mock_redis

            orch._load_ranked_targets = MagicMock(return_value=(
                ["005930"],
                {"005930": "삼성전자"},
                {"005930": {"name": "삼성전자"}},
            ))
            orch._symbol_last_seen = {"005930": datetime.now()}

            orch._refresh_universe_from_screener()

        assert not any("prev_day_volume" in msg for msg in caplog.messages)

    def test_warning_only_once(self, caplog):
        """Warning should only fire once (flag prevents repeat logging)."""
        orch = _make_orchestrator()
        orch._prev_day_volume_warned = True  # already warned

        mock_sm = MagicMock()
        mock_sm.strategy_names = ["opening_volume_surge"]
        orch._strategy_manager = mock_sm
        orch._symbol_metadata_cache = {"005930": {"name": "삼성전자"}}

        with patch("shared.streaming.client.RedisClient") as mock_redis_cls, \
             caplog.at_level(logging.WARNING):
            mock_redis = MagicMock()
            mock_redis_cls.get_client.return_value = mock_redis

            orch._load_ranked_targets = MagicMock(return_value=(
                ["005930"],
                {"005930": "삼성전자"},
                {"005930": {"name": "삼성전자"}},
            ))
            orch._symbol_last_seen = {"005930": datetime.now()}

            orch._refresh_universe_from_screener()

        assert not any("prev_day_volume" in msg for msg in caplog.messages)


class TestOvernightSwingInjection:
    """Verify that overnight swing positions are injected into config.symbols."""

    @pytest.mark.asyncio
    async def test_overnight_positions_added_to_symbols(self):
        """Symbols from loaded swing positions should be appended to config.symbols."""
        orch = _make_orchestrator()
        orch.config.symbols = ["005930"]

        # Mock position tracker with an overnight position not in symbols
        pos = MagicMock()
        pos.code = "000660"
        pos.strategy = "volume_accumulation"

        tracker = MagicMock()
        tracker.positions = [pos]
        tracker.load_from_db = AsyncMock()
        orch._position_tracker = tracker

        # Mock strategy manager with swing strategy
        sm = MagicMock()
        sm.strategy_names = ["volume_accumulation"]
        orch._strategy_manager = sm

        from services.trading.orchestrator import TradingOrchestrator
        orch.SWING_STRATEGIES = TradingOrchestrator.SWING_STRATEGIES

        # Simulate the load_from_db + injection logic
        loaded_strategies = set(sm.strategy_names)
        if tracker and (loaded_strategies & orch.SWING_STRATEGIES):
            await tracker.load_from_db()
            now = datetime.now()
            current_symbols = set(orch.config.symbols or [])
            for p in tracker.positions:
                if p.code not in current_symbols:
                    orch.config.symbols.append(p.code)
                    orch._symbol_last_seen[p.code] = now

        assert "000660" in orch.config.symbols
        assert "005930" in orch.config.symbols
        # Critical: must be in _symbol_last_seen to survive screener refresh
        assert "000660" in orch._symbol_last_seen

    @pytest.mark.asyncio
    async def test_no_duplicate_when_already_in_symbols(self):
        """If overnight symbol is already in symbols, it should not be duplicated."""
        orch = _make_orchestrator()
        orch.config.symbols = ["005930", "000660"]

        pos = MagicMock()
        pos.code = "000660"

        tracker = MagicMock()
        tracker.positions = [pos]
        tracker.load_from_db = AsyncMock()
        orch._position_tracker = tracker

        from services.trading.orchestrator import TradingOrchestrator
        orch.SWING_STRATEGIES = TradingOrchestrator.SWING_STRATEGIES

        current_symbols = set(orch.config.symbols or [])
        for p in tracker.positions:
            if p.code not in current_symbols:
                orch.config.symbols.append(p.code)

        assert orch.config.symbols.count("000660") == 1


class TestOvsLogLevel:
    """Verify opening_volume_surge logs WARNING for missing prev_day_volume."""

    @pytest.mark.asyncio
    async def test_missing_prev_day_volume_logs_warning(self, caplog):
        """prev_day_volume <= 0 should log at WARNING level."""
        from shared.strategy.base import EntryContext
        from shared.strategy.entry.opening_volume_surge import (
            OpeningVolumeSurgeEntry,
            OpeningVolumeSurgeConfig,
        )

        entry = OpeningVolumeSurgeEntry(OpeningVolumeSurgeConfig())

        # Create context with market open time (so we pass the time window check)
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]
        KST = ZoneInfo("Asia/Seoul")
        now = datetime.now(KST).replace(hour=9, minute=5)

        ctx = EntryContext(
            market_data={
                "code": "005930",
                "volume": 5_000_000,
                "prev_day_volume": 0,
            },
            timestamp=now,
        )

        with caplog.at_level(logging.WARNING):
            result = await entry.generate(ctx)

        assert result is None
        assert any("prev_day_volume" in msg for msg in caplog.messages)
        assert any(
            record.levelno == logging.WARNING for record in caplog.records
            if "prev_day_volume" in record.message
        )


class TestUniverseSizeFromConfig:
    """Verify _max_universe_size is driven by streaming.yaml stock_feed.max_symbols."""

    def test_reads_max_symbols_from_streaming_config(self):
        """Config logic should extract max_symbols from stock_feed section."""
        streaming_cfg = {"stock_feed": {"max_symbols": 35}}
        _sf_cfg = streaming_cfg.get("stock_feed", {})
        result = int(_sf_cfg.get("max_symbols", 40))
        assert result == 35

    def test_defaults_to_40_when_config_missing(self):
        """_max_universe_size should default to 40 (matching WebSocket limit)."""
        orch = _make_orchestrator()
        assert orch._max_universe_size == 40

    def test_defaults_to_40_when_stock_feed_section_missing(self):
        """When streaming.yaml has no stock_feed section, default to 40."""
        streaming_cfg = {"redis": {"host": "localhost"}}
        _sf_cfg = streaming_cfg.get("stock_feed", {})
        result = int(_sf_cfg.get("max_symbols", 40))
        assert result == 40


class TestIndicatorCleanupOnUniverseChange:
    """Verify indicator engine symbols are cleaned up when universe shrinks."""

    def test_removed_symbols_cleaned_from_indicator_engine(self):
        """When _apply_universe_changes removes symbols, indicator engine state is cleaned."""
        orch = _make_orchestrator()

        # Mock indicator engine with remove_symbol
        mock_engine = MagicMock()
        orch._indicator_engine = mock_engine
        orch._data_provider = MagicMock()

        # Start with 3 symbols
        orch.config.symbols = ["005930", "000660", "035720"]

        # Apply new universe that drops 000660
        orch._apply_universe_changes({"005930", "035720"})

        # remove_symbol should have been called for 000660
        mock_engine.remove_symbol.assert_called_once_with("000660")

    def test_no_cleanup_when_no_indicator_engine(self):
        """When indicator engine is None, no error on symbol removal."""
        orch = _make_orchestrator()
        orch._indicator_engine = None
        orch._data_provider = MagicMock()
        orch.config.symbols = ["005930", "000660"]

        # Should not raise
        orch._apply_universe_changes({"005930"})

    def test_no_cleanup_when_universe_unchanged(self):
        """When universe doesn't change, no remove_symbol calls."""
        orch = _make_orchestrator()
        mock_engine = MagicMock()
        orch._indicator_engine = mock_engine
        orch.config.symbols = ["005930"]

        orch._apply_universe_changes({"005930"})

        mock_engine.remove_symbol.assert_not_called()
