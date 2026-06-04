"""Unit tests for pipeline observability gaps — feed drop warnings and warmup misses.

Tests verify:
- A: Feed drop delta triggers logger.warning when drop_warn_threshold is reached.
- A: Feed stale data triggers logger.warning when stale_warn_threshold_seconds is reached.
- A: Key-name normalisation: stock uses 'dropped_count', futures uses 'messages_dropped'.
- B: Warmup returning 0 bars logs a WARNING and increments the warmup_miss_count.
- B: Warmup returning fewer bars than warmup_min_candles also warns + increments.
- B: _fetch_candles_from_clickhouse exception emits WARNING (not just debug).

No hardcoded datetimes; no real network/Redis/ClickHouse connections used.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / minimal stubs
# ---------------------------------------------------------------------------


def _make_minimal_orchestrator(asset_class: str = "stock"):
    """Create a TradingOrchestrator with a minimal fake config.

    Avoids real network connections by patching heavy initialisation.
    We only test _record_market_metrics and _prewarm_symbols behaviours here.
    """
    from services.trading.orchestrator import TradingConfig, TradingOrchestrator

    config = TradingConfig(
        asset_class=asset_class,
        strategy_name="bb_reversion",
        symbols=["A000000"] if asset_class == "stock" else ["A05603"],
        initial_capital=10_000_000,
        paper_trading=True,
    )

    with patch.object(
        TradingOrchestrator, "_load_entry_reentry_guard_config", return_value={}
    ):
        orch = object.__new__(TradingOrchestrator)
        # Initialise only the attributes our tested methods read.
        orch.config = config
        orch._market_data_snapshot = {}
        orch._market_data_updated_at = None
        orch._stock_price_feed = None
        orch._futures_price_feed = None
        orch._indicator_engine = None
        orch._tick_stream_publisher = None
        orch._position_tracker = None
        orch._feed_drop_last = {"stock": 0, "futures": 0}
        orch._warmup_miss_count = 0
        orch._feed_obs_cfg = None  # will be loaded lazily

    # Attach a mock metrics collector so we don't need prometheus installed.
    mock_metrics = MagicMock()
    orch._metrics = mock_metrics
    return orch


def _patch_feed_obs_cfg(orch, cfg_overrides: dict | None = None):
    """Directly set _feed_obs_cfg to avoid ConfigLoader in tests."""
    defaults = {
        "drop_warn_threshold": 1,
        "stale_warn_threshold_seconds": 60.0,
        "warmup_min_candles": 20,
    }
    if cfg_overrides:
        defaults.update(cfg_overrides)
    orch._feed_obs_cfg = defaults


# ---------------------------------------------------------------------------
# ITEM A: Feed drop delta warning tests
# ---------------------------------------------------------------------------


class TestFeedDropWarnings:
    """A: _record_market_metrics emits warnings when feed drops increase."""

    def test_stock_drop_delta_triggers_warning(self, caplog):
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch, {"drop_warn_threshold": 1})

        # Stock feed reports 5 cumulative drops.
        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 0.5
        mock_feed.get_health_status.return_value = {
            "dropped_count": 5,
            "staleness_seconds": 0.5,
        }
        orch._stock_price_feed = mock_feed

        with caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"):
            orch._record_market_metrics()

        assert any(
            "stock feed dropped" in r.message for r in caplog.records
        ), "Expected WARNING about stock feed drops, but none was logged"
        assert orch._feed_drop_last["stock"] == 5

    def test_stock_drop_no_warning_when_delta_zero(self, caplog):
        """If drops haven't increased since last check, no warning emitted."""
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch, {"drop_warn_threshold": 1})
        orch._feed_drop_last["stock"] = 5  # already seen 5 drops

        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 0.5
        mock_feed.get_health_status.return_value = {"dropped_count": 5}
        orch._stock_price_feed = mock_feed

        with caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"):
            orch._record_market_metrics()

        drop_warnings = [
            r
            for r in caplog.records
            if "dropped" in r.message and r.levelno >= logging.WARNING
        ]
        assert not drop_warnings, "No drop warning expected when delta is zero"

    def test_futures_drop_delta_triggers_warning(self, caplog):
        """A: futures feed uses 'messages_dropped' key (not 'dropped_count')."""
        orch = _make_minimal_orchestrator("futures")
        _patch_feed_obs_cfg(orch, {"drop_warn_threshold": 1})

        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 1.0
        mock_feed.get_health_status.return_value = {
            "messages_dropped": 3,
        }
        orch._futures_price_feed = mock_feed

        with caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"):
            orch._record_market_metrics()

        assert any(
            "futures feed dropped" in r.message for r in caplog.records
        ), "Expected WARNING about futures feed drops"
        assert orch._feed_drop_last["futures"] == 3

    def test_futures_key_name_normalised(self):
        """A: futures health dict uses 'messages_dropped', not 'dropped_count'.
        Confirm orchestrator reads the correct key (no silent miss).
        """
        orch = _make_minimal_orchestrator("futures")
        _patch_feed_obs_cfg(orch, {"drop_warn_threshold": 1})

        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 0.5
        # Deliberately provide only the futures key; dropped_count is absent.
        mock_feed.get_health_status.return_value = {
            "messages_dropped": 7,
            # 'dropped_count' intentionally absent
        }
        orch._futures_price_feed = mock_feed

        orch._record_market_metrics()

        assert (
            orch._feed_drop_last["futures"] == 7
        ), "Orchestrator should read 'messages_dropped' (futures adapter key)"

    def test_metrics_collector_called_with_feed_drop_delta(self):
        """A: record_feed_drops is called with the delta (not cumulative total).

        Baseline is 0, feed reports 10 drops → delta = 10.
        """
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch)

        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 0.5
        mock_feed.get_health_status.return_value = {"dropped_count": 10}
        orch._stock_price_feed = mock_feed

        orch._record_market_metrics()

        # Orchestrator passes delta (new drops since last check), not cumulative.
        orch._metrics.record_feed_drops.assert_called_with("stock", 10)

    def test_stale_feed_triggers_warning(self, caplog):
        """A: staleness above threshold emits WARNING."""
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch, {"stale_warn_threshold_seconds": 60.0})

        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 90.0  # above threshold
        mock_feed.get_health_status.return_value = {"dropped_count": 0}
        orch._stock_price_feed = mock_feed

        with caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"):
            orch._record_market_metrics()

        assert any(
            "stale" in r.message for r in caplog.records
        ), "Expected WARNING about stale stock feed"

    def test_non_stale_feed_no_stale_warning(self, caplog):
        """A: staleness below threshold does NOT emit WARNING."""
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch, {"stale_warn_threshold_seconds": 60.0})

        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 10.0  # well below threshold
        mock_feed.get_health_status.return_value = {"dropped_count": 0}
        orch._stock_price_feed = mock_feed

        with caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"):
            orch._record_market_metrics()

        stale_warnings = [
            r
            for r in caplog.records
            if "stale" in r.message and r.levelno >= logging.WARNING
        ]
        assert not stale_warnings

    def test_feed_health_error_does_not_raise(self):
        """A: if get_health_status raises, _record_market_metrics is resilient."""
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch)

        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 1.0
        mock_feed.get_health_status.side_effect = RuntimeError("feed unavailable")
        orch._stock_price_feed = mock_feed

        # Must not raise
        orch._record_market_metrics()


# ---------------------------------------------------------------------------
# ITEM B: Warmup miss warning tests
# ---------------------------------------------------------------------------


class TestWarmupMissWarnings:
    """B: _prewarm_symbols warns when a symbol returns 0 or too few bars."""

    @pytest.mark.asyncio
    async def test_zero_bars_logs_warning_and_increments_counter(self, caplog):
        """B: symbol returning 0 bars from all sources → WARNING + miss counter."""
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch, {"warmup_min_candles": 20})

        # Indicator engine says symbol is not warm.
        mock_ie = MagicMock()
        mock_ie.is_warm.return_value = False
        orch._indicator_engine = mock_ie

        # KIS client not rate limited, but returns nothing.
        mock_kis = MagicMock()
        mock_kis.is_rate_limited = False
        mock_kis.get_minute_bars = AsyncMock(return_value=[])
        orch._kis_client = mock_kis

        # Mock dependencies for _prewarm_symbols internals.
        orch._load_candle_cache_from_redis = AsyncMock(return_value=0)
        orch._fetch_candles_from_clickhouse = AsyncMock(return_value=[])
        orch._fetch_daily_candles_from_clickhouse = AsyncMock(return_value=[])

        with caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"):
            await orch._prewarm_symbols(["A000000"])

        assert (
            orch._warmup_miss_count == 1
        ), "Miss counter should be 1 after zero-bar warmup"
        warning_msgs = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert any(
            "no candles returned" in m for m in warning_msgs
        ), f"Expected 'no candles returned' warning; got: {warning_msgs}"
        orch._metrics.record_warmup_miss.assert_called()

    @pytest.mark.asyncio
    async def test_below_min_candles_logs_warning(self, caplog):
        """B: symbol returning fewer bars than warmup_min_candles warns + increments."""
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch, {"warmup_min_candles": 20})

        mock_ie = MagicMock()
        mock_ie.is_warm.return_value = False
        mock_ie.seed_candles = MagicMock()
        orch._indicator_engine = mock_ie

        # ClickHouse returns 5 bars (below min 20).
        sparse_candles = [
            {
                "datetime": "2026-05-01 09:00",
                "open": 1,
                "high": 1,
                "low": 1,
                "close": 1,
                "volume": 1,
            }
            for _ in range(5)
        ]
        orch._load_candle_cache_from_redis = AsyncMock(return_value=0)
        orch._fetch_candles_from_clickhouse = AsyncMock(return_value=sparse_candles)
        orch._fetch_daily_candles_from_clickhouse = AsyncMock(return_value=[])

        with caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"):
            await orch._prewarm_symbols(["A000000"])

        assert orch._warmup_miss_count == 1
        warning_msgs = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert any(
            "under-initialised" in m or "only" in m for m in warning_msgs
        ), f"Expected under-initialised warning; got: {warning_msgs}"
        orch._metrics.record_warmup_miss.assert_called()

    @pytest.mark.asyncio
    async def test_sufficient_candles_no_miss(self, caplog):
        """B: symbol returning >= warmup_min_candles bars does NOT trigger miss."""
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch, {"warmup_min_candles": 5})

        mock_ie = MagicMock()
        mock_ie.is_warm.return_value = False
        mock_ie.seed_candles = MagicMock()
        orch._indicator_engine = mock_ie

        enough_candles = [
            {
                "datetime": "2026-05-01 09:00",
                "open": 1,
                "high": 1,
                "low": 1,
                "close": 1,
                "volume": 1,
            }
            for _ in range(10)
        ]
        orch._load_candle_cache_from_redis = AsyncMock(return_value=0)
        orch._fetch_candles_from_clickhouse = AsyncMock(return_value=enough_candles)
        orch._fetch_daily_candles_from_clickhouse = AsyncMock(return_value=[])

        with caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"):
            await orch._prewarm_symbols(["A000000"])

        assert orch._warmup_miss_count == 0
        orch._metrics.record_warmup_miss.assert_not_called()

    @pytest.mark.asyncio
    async def test_clickhouse_exception_emits_warning_not_debug(self, caplog):
        """B: _fetch_candles_from_clickhouse exception → WARNING (not just DEBUG)."""
        orch = _make_minimal_orchestrator("stock")

        # Patch the executor so we can simulate a connection error without real infra.
        with patch("asyncio.get_event_loop") as mock_loop:
            # Make the executor call raise an OSError (connection refused).
            mock_loop.return_value.run_in_executor = AsyncMock(
                side_effect=OSError("Connection refused")
            )

            with caplog.at_level(
                logging.WARNING, logger="services.trading.orchestrator"
            ):
                result = await orch._fetch_candles_from_clickhouse("A000000", limit=120)

        assert result == [], "Exception should return empty list"
        warning_msgs = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any(
            "prewarm" in r.message.lower() for r in warning_msgs
        ), f"Expected WARNING about ClickHouse prewarm failure; got: {[r.message for r in caplog.records]}"

    @pytest.mark.asyncio
    async def test_multiple_symbols_accumulate_miss_count(self):
        """B: misses from multiple symbols accumulate in _warmup_miss_count."""
        symbols = ["A000001", "A000002", "A000003"]
        orch = _make_minimal_orchestrator("stock")
        # Override config.symbols so the eviction guard doesn't skip the test symbols.
        orch.config = MagicMock()
        orch.config.symbols = symbols
        orch.config.asset_class = "stock"
        _patch_feed_obs_cfg(orch, {"warmup_min_candles": 20})

        mock_ie = MagicMock()
        mock_ie.is_warm.return_value = False
        orch._indicator_engine = mock_ie

        mock_kis = MagicMock()
        mock_kis.is_rate_limited = False
        mock_kis.get_minute_bars = AsyncMock(return_value=[])

        orch._kis_client = mock_kis
        orch._load_candle_cache_from_redis = AsyncMock(return_value=0)
        orch._fetch_candles_from_clickhouse = AsyncMock(return_value=[])
        orch._fetch_daily_candles_from_clickhouse = AsyncMock(return_value=[])

        await orch._prewarm_symbols(symbols)

        assert orch._warmup_miss_count == 3
        assert orch._metrics.record_warmup_miss.call_count == 3


# ---------------------------------------------------------------------------
# ITEM A + B integration: get_status includes feed_drops and warmup_misses
# ---------------------------------------------------------------------------


class TestStatusIncludesFeedHealth:
    """A+B: get_status() exposes feed_drops and warmup_misses."""

    def test_get_status_contains_feed_drops_and_warmup_misses(self):
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(orch)

        orch._feed_drop_last = {"stock": 7, "futures": 0}
        orch._warmup_miss_count = 2

        # Stub out everything get_status reads.
        orch.state = MagicMock()
        orch.state.value = "running"
        orch._current_regime = "BULL"
        orch.session_count = 0
        orch.total_trades = 0
        orch.total_pnl = 0.0
        orch._mock_mirror_stats = {}
        orch._entry_slippage_stats = {"count": 0.0, "avg_adverse_ticks": 0.0}
        orch.start_time = None
        orch._position_tracker = None
        orch._strategy_manager = None
        orch._data_provider = None
        orch.pipeline = None
        orch._paper_broker = None
        orch._risk_manager = None

        status = orch.get_status()

        assert status["stats"]["feed_drops"] == {"stock": 7, "futures": 0}
        assert status["stats"]["warmup_misses"] == 2


# ---------------------------------------------------------------------------
# NEW FIX 4: Real-object tests — adapter counters, feed propagation, restart clamp
# ---------------------------------------------------------------------------


class TestRealAdapterDropCounters:
    """Fix 4: Tests using a REAL KISWebSocketAdapter to prevent regression.

    These tests would FAIL if someone reverted _messages_dropped to hardcoded 0.
    """

    def _make_real_adapter(self):
        """Construct a real KISWebSocketAdapter without a network connection."""
        from unittest.mock import patch

        from shared.kis.auth import KISAuthConfig
        from shared.kis.websocket import KISWebSocketAdapter

        config = KISAuthConfig(
            app_key="test_key",
            app_secret="test_secret",
            is_real=False,
        )
        with patch("shared.kis.websocket.websocket.WebSocketApp"):
            return KISWebSocketAdapter(config)

    def test_adapter_initial_counters_are_zero(self):
        """Real adapter starts with messages_received=0 and messages_dropped=0."""
        adapter = self._make_real_adapter()
        status = adapter.get_health_status()
        assert "messages_received" in status, "messages_received key must be present"
        assert "messages_dropped" in status, "messages_dropped key must be present"
        assert status["messages_received"] == 0
        assert status["messages_dropped"] == 0

    def test_adapter_messages_received_increments_on_message(self):
        """Each _on_message call increments messages_received."""
        adapter = self._make_real_adapter()
        adapter._on_message(None, "msg1")
        adapter._on_message(None, "msg2")
        adapter._on_message(None, "msg3")

        status = adapter.get_health_status()
        assert status["messages_received"] == 3

    def test_adapter_messages_dropped_increments_on_queue_full(self):
        """When the queue is full, messages_dropped increments by 1 per overflow."""
        import queue as _queue

        adapter = self._make_real_adapter()

        # Fill the queue to capacity with dummy messages so put_nowait raises Full.
        while True:
            try:
                adapter._message_queue.put_nowait("filler")
            except _queue.Full:
                break

        received_before = adapter.get_health_status()["messages_received"]
        dropped_before = adapter.get_health_status()["messages_dropped"]

        # This message should trigger the queue.Full path.
        adapter._on_message(None, "overflow_msg")

        status = adapter.get_health_status()
        assert status["messages_received"] == received_before + 1
        assert status["messages_dropped"] == dropped_before + 1, (
            "messages_dropped must increase by 1 when queue is full; "
            "reverted to hardcoded 0?"
        )

    def test_adapter_no_drops_without_overflow(self):
        """Normal message delivery does not increment messages_dropped."""
        adapter = self._make_real_adapter()
        # Drain queue so put_nowait always succeeds.
        import queue as _queue

        while not adapter._message_queue.empty():
            try:
                adapter._message_queue.get_nowait()
            except _queue.Empty:
                break

        adapter._on_message(None, "msg1")
        adapter._on_message(None, "msg2")

        status = adapter.get_health_status()
        assert status["messages_dropped"] == 0


class TestFuturesFeedPropagatesAdapterDrops:
    """Fix 4: Real KISFuturesPriceFeed.get_health_status() must expose messages_dropped."""

    def test_futures_feed_health_includes_messages_dropped(self):
        """messages_dropped must appear in futures feed health (spread from adapter)."""
        from unittest.mock import patch

        from shared.kis.auth import KISAuthConfig

        config = KISAuthConfig(
            app_key="test_key",
            app_secret="test_secret",
            is_real=False,
        )

        with (
            patch("shared.kis.websocket.websocket.WebSocketApp"),
            patch(
                "shared.kis.futures_feed._load_futures_feed_config",
                return_value={
                    "max_symbols": 10,
                    "subscription_delay": 0.1,
                    "connection_timeout": 5.0,
                    "shutdown_timeout": 5.0,
                    "orderbook_stale_threshold_seconds": 3.0,
                    "orderbook_missing_warn_interval_seconds": 30.0,
                },
            ),
        ):
            from shared.kis.futures_feed import KISFuturesPriceFeed

            feed = KISFuturesPriceFeed(config)

        status = feed.get_health_status()
        assert "messages_dropped" in status, (
            "KISFuturesPriceFeed.get_health_status() must expose 'messages_dropped' "
            "from the adapter — key is missing, did Feed.get_health_status() lose the spread?"
        )
        assert (
            "messages_received" in status
        ), "KISFuturesPriceFeed.get_health_status() must expose 'messages_received' from adapter"

    def test_futures_feed_health_adapter_drops_reflect_real_counter(self):
        """messages_dropped in feed health reflects real adapter counter (not 0)."""
        import queue as _queue
        from unittest.mock import patch

        from shared.kis.auth import KISAuthConfig

        config = KISAuthConfig(
            app_key="test_key",
            app_secret="test_secret",
            is_real=False,
        )

        with (
            patch("shared.kis.websocket.websocket.WebSocketApp"),
            patch(
                "shared.kis.futures_feed._load_futures_feed_config",
                return_value={
                    "max_symbols": 10,
                    "subscription_delay": 0.1,
                    "connection_timeout": 5.0,
                    "shutdown_timeout": 5.0,
                    "orderbook_stale_threshold_seconds": 3.0,
                    "orderbook_missing_warn_interval_seconds": 30.0,
                },
            ),
        ):
            from shared.kis.futures_feed import KISFuturesPriceFeed

            feed = KISFuturesPriceFeed(config)

        # Fill adapter queue to force a drop.
        while True:
            try:
                feed._adapter._message_queue.put_nowait("filler")
            except _queue.Full:
                break
        feed._adapter._on_message(None, "overflow")

        status = feed.get_health_status()
        assert (
            status["messages_dropped"] == 1
        ), "Feed health must reflect actual drop count from adapter"


class TestDeltaClampRestartSafety:
    """Fix 4: Delta clamp prevents negative delta when feed restarts."""

    def test_counter_backward_resets_baseline_and_warns(self, caplog):
        """If total drops go backwards (feed restarted), delta = new total, not negative."""
        import logging

        orch = _make_minimal_orchestrator("futures")
        _patch_feed_obs_cfg(orch, {"drop_warn_threshold": 1})
        # Simulate prior session: 50 drops seen
        orch._feed_drop_last["futures"] = 50

        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 0.5
        # Feed restarted: counter reset to 3 (< 50 → backwards)
        mock_feed.get_health_status.return_value = {"messages_dropped": 3}
        orch._futures_price_feed = mock_feed

        with caplog.at_level(logging.WARNING, logger="services.trading.orchestrator"):
            orch._record_market_metrics()

        # Baseline should have been reset to 0, delta = 3, so WARNING fires.
        assert orch._feed_drop_last["futures"] == 3
        assert any(
            "futures feed dropped" in r.message for r in caplog.records
        ), "After restart, the new drops (delta=3) should trigger a warning"
        # record_feed_drops called with delta=3 (not -47)
        orch._metrics.record_feed_drops.assert_called_with("futures", 3)

    def test_counter_backward_stock_resets_baseline(self):
        """Stock: backwards counter triggers baseline reset; no negative delta."""
        orch = _make_minimal_orchestrator("stock")
        _patch_feed_obs_cfg(
            orch, {"drop_warn_threshold": 100}
        )  # high threshold → no warning
        orch._feed_drop_last["stock"] = 100

        mock_feed = MagicMock()
        mock_feed.get_staleness_seconds.return_value = 0.5
        mock_feed.get_health_status.return_value = {"dropped_count": 5}
        orch._stock_price_feed = mock_feed

        orch._record_market_metrics()

        # baseline reset → delta = 5, no warning (threshold=100), but counter updated
        assert orch._feed_drop_last["stock"] == 5
        orch._metrics.record_feed_drops.assert_called_with("stock", 5)
