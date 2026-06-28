"""Trading Orchestrator 테스트"""

from datetime import date, time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestIsTradingDay:
    """is_trading_day 함수 테스트"""

    def test_weekday_is_trading_day(self):
        """평일은 거래일"""
        from services.trading.orchestrator import is_trading_day

        # 2024-01-15 월요일
        monday = date(2024, 1, 15)
        assert is_trading_day(monday, holidays=set()) is True

    def test_weekend_is_not_trading_day(self):
        """주말은 거래일 아님"""
        from services.trading.orchestrator import is_trading_day

        # 2024-01-13 토요일
        saturday = date(2024, 1, 13)
        assert is_trading_day(saturday, holidays=set()) is False

        # 2024-01-14 일요일
        sunday = date(2024, 1, 14)
        assert is_trading_day(sunday, holidays=set()) is False

    def test_holiday_is_not_trading_day(self):
        """공휴일은 거래일 아님"""
        from services.trading.orchestrator import is_trading_day

        new_year = date(2024, 1, 1)
        holidays = {new_year}
        assert is_trading_day(new_year, holidays=holidays) is False


class TestMarketSchedule:
    """MarketSchedule 클래스 테스트"""

    def test_default_stock_hours(self):
        """기본 주식 거래 시간"""
        from services.trading.orchestrator import MarketSchedule

        schedule = MarketSchedule()
        assert schedule.stock_open == time(9, 0)
        assert schedule.stock_close == time(15, 30)

    def test_default_futures_hours(self):
        """기본 선물 거래 시간 (08:45 KRX 정규장 개장)"""
        from services.trading.orchestrator import MarketSchedule

        schedule = MarketSchedule()
        assert schedule.futures_open == time(8, 45)
        assert schedule.futures_close == time(15, 45)

    def test_get_open_time(self):
        """개장 시간 조회"""
        from services.trading.orchestrator import MarketSchedule

        schedule = MarketSchedule()
        assert schedule.get_open_time("stock") == time(9, 0)
        assert schedule.get_open_time("futures") == time(8, 45)

    def test_get_close_time(self):
        """폐장 시간 조회"""
        from services.trading.orchestrator import MarketSchedule

        schedule = MarketSchedule()
        assert schedule.get_close_time("stock") == time(15, 30)
        assert schedule.get_close_time("futures") == time(15, 45)


class TestTradingConfig:
    """TradingConfig 클래스 테스트"""

    def test_stock_factory(self):
        """주식 설정 팩토리"""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig.stock(
            strategy_name="test_strategy",
            symbols=["005930", "000660"],
            initial_capital=10_000_000,
        )

        assert config.asset_class == "stock"
        assert config.strategy_name == "test_strategy"
        assert config.symbols == ["005930", "000660"]
        assert config.initial_capital == 10_000_000
        assert config.require_daily_indicators_for_dynamic_universe is True
        assert config.regime_exclude_dip_candidates is True
        assert config.regime_exclude_position_only_symbols is True
        assert config.regime_require_daily_indicators is True
        assert config.regime_require_mfi_symbols is True

    def test_stock_factory_allows_dynamic_universe_coverage_override(self):
        """주식 동적 유니버스 daily indicator 커버리지 가드를 설정으로 끌 수 있다."""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig.stock(
            require_daily_indicators_for_dynamic_universe=False
        )

        assert config.require_daily_indicators_for_dynamic_universe is False

    def test_stock_factory_allows_daily_watchlist_merge_override(self):
        """주식 동적 유니버스 daily watchlist 병합을 설정으로 끌 수 있다."""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig.stock(include_daily_watchlist_in_dynamic_universe=False)

        assert config.include_daily_watchlist_in_dynamic_universe is False

    def test_stock_factory_allows_daily_entry_warmup_bypass_override(self):
        """주식 daily watchlist 엔트리 warmup 우회를 설정으로 끌 수 있다."""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig.stock(
            allow_daily_watchlist_entry_before_intraday_warmup=False
        )

        assert config.allow_daily_watchlist_entry_before_intraday_warmup is False

    def test_stock_factory_allows_regime_filter_overrides(self):
        """주식 레짐 유니버스 필터를 설정으로 끌 수 있다."""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig.stock(
            regime_exclude_dip_candidates=False,
            regime_exclude_position_only_symbols=False,
            regime_require_daily_indicators=False,
            regime_require_mfi_symbols=False,
            regime_min_mfi_symbols=4,
            regime_min_mfi_coverage_ratio=0.25,
            regime_low_confidence_bear_fallback="SIDEWAYS_FLAT",
        )

        assert config.regime_exclude_dip_candidates is False
        assert config.regime_exclude_position_only_symbols is False
        assert config.regime_require_daily_indicators is False
        assert config.regime_require_mfi_symbols is False
        assert config.regime_min_mfi_symbols == 4
        assert config.regime_min_mfi_coverage_ratio == 0.25
        assert config.regime_low_confidence_bear_fallback == "SIDEWAYS_FLAT"

    def test_futures_factory(self):
        """선물 설정 팩토리"""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig.futures(
            strategy_name="pure_micro",
            initial_capital=5_000_000,
        )

        assert config.asset_class == "futures"
        assert config.strategy_name == "pure_micro"
        assert config.initial_capital == 5_000_000


class TestRiskCapitalAlignment:
    def test_runtime_capital_overrides_shared_default_without_env(self, monkeypatch):
        from services.trading.orchestrator import _risk_params_for_runtime_capital

        monkeypatch.delenv("RISK_INITIAL_CAPITAL", raising=False)

        params = _risk_params_for_runtime_capital(
            {"daily_loss_limit_pct": 5.0, "initial_capital": 10_000_000},
            100_000_000,
        )

        assert params["initial_capital"] == 100_000_000

    def test_explicit_risk_capital_env_preserves_risk_config(self, monkeypatch):
        from services.trading.orchestrator import _risk_params_for_runtime_capital

        monkeypatch.setenv("RISK_INITIAL_CAPITAL", "50000000")

        params = _risk_params_for_runtime_capital(
            {"daily_loss_limit_pct": 5.0, "initial_capital": 50_000_000},
            100_000_000,
        )

        assert params["initial_capital"] == 50_000_000

    def test_alignment_does_not_mutate_loaded_config(self, monkeypatch):
        from services.trading.orchestrator import _risk_params_for_runtime_capital

        monkeypatch.delenv("RISK_INITIAL_CAPITAL", raising=False)
        loaded = {"daily_loss_limit_pct": 5.0, "initial_capital": 10_000_000}

        params = _risk_params_for_runtime_capital(loaded, 100_000_000)

        assert loaded["initial_capital"] == 10_000_000
        assert params["initial_capital"] == 100_000_000


class TestNextSessionWake:
    """데몬 다음-세션 기상 = 설정된 개장 − service_start_offset (자산별)."""

    def test_futures_wake_0840(self):
        """선물 08:45 개장 − 5분 offset → 08:40 기상 (구 하드코딩 08:55 대체)."""
        from datetime import datetime

        from services.trading.orchestrator import TradingOrchestrator

        now = datetime(2026, 6, 28, 23, 43)  # naive (container TZ=KST)
        wake = TradingOrchestrator._next_session_wake(now, time(8, 45), 5)
        assert wake == datetime(2026, 6, 29, 8, 40)

    def test_stock_wake_0855_unchanged(self):
        """주식 09:00 개장 − 5분 → 08:55 (기존 동작 보존)."""
        from datetime import datetime

        from services.trading.orchestrator import TradingOrchestrator

        now = datetime(2026, 6, 28, 23, 43)
        wake = TradingOrchestrator._next_session_wake(now, time(9, 0), 5)
        assert wake == datetime(2026, 6, 29, 8, 55)

    def test_wake_uses_schedule_open(self):
        """실제 MarketSchedule 개장 시각을 따른다 (08:45 선물)."""
        from datetime import datetime

        from services.trading.orchestrator import MarketSchedule, TradingOrchestrator

        sched = MarketSchedule()
        now = datetime(2026, 6, 28, 23, 43)
        wake = TradingOrchestrator._next_session_wake(
            now, sched.get_open_time("futures"), sched.service_start_offset_minutes
        )
        assert wake == datetime(2026, 6, 29, 8, 40)


class TestTradingOrchestrator:
    """TradingOrchestrator 클래스 테스트"""

    def test_init(self):
        """초기화"""
        from services.trading.orchestrator import (
            TradingConfig,
            TradingOrchestrator,
            TradingState,
        )

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        assert orch.state == TradingState.IDLE
        assert orch.session_count == 0
        assert orch.total_trades == 0

    def test_is_running_when_idle(self):
        """IDLE 상태에서 is_running"""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        assert orch.is_running is False

    @pytest.mark.asyncio
    async def test_start_changes_state(self, monkeypatch):
        """start() 호출 시 상태 변경"""
        from services.monitoring.metrics import MetricsCollector
        from services.trading.orchestrator import (
            TradingConfig,
            TradingOrchestrator,
            TradingState,
        )

        monkeypatch.setattr(
            MetricsCollector, "start_prometheus_server", lambda *a, **kw: None
        )

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        await orch.start()
        assert orch.state == TradingState.RUNNING

        await orch.stop()

    @pytest.mark.asyncio
    async def test_stop_changes_state(self, monkeypatch):
        """stop() 호출 시 상태 변경"""
        from services.monitoring.metrics import MetricsCollector
        from services.trading.orchestrator import (
            TradingConfig,
            TradingOrchestrator,
            TradingState,
        )

        monkeypatch.setattr(
            MetricsCollector, "start_prometheus_server", lambda *a, **kw: None
        )
        monkeypatch.setattr(
            TradingOrchestrator, "_init_llm_context_publisher", lambda *a, **kw: None
        )

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        await orch.start()
        await orch.stop()

        assert orch.state == TradingState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_sets_interrupt_flag_even_when_already_stopped(self):
        """STOPPED 상태에서도 daemon sleep을 깨울 수 있도록 stop intent를 기록한다."""
        from services.trading.orchestrator import (
            TradingConfig,
            TradingOrchestrator,
            TradingState,
        )

        orch = TradingOrchestrator(TradingConfig.stock())
        orch.state = TradingState.STOPPED
        orch._running = True

        await orch.stop()

        assert orch._stop_requested is True
        assert orch._running is False

    @pytest.mark.asyncio
    async def test_daemon_run_exits_without_next_session_sleep_when_session_stops(
        self, monkeypatch
    ):
        """장 종료 stop 후 다음 세션 sleep에 들어가지 않고 프로세스를 종료한다."""
        import services.trading.orchestrator as orchestrator_module
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        orch = TradingOrchestrator(TradingConfig.stock())
        orch._notify = AsyncMock()

        async def fake_run_session():
            orch._stop_requested = True
            orch._running = False

        async def unexpected_sleep(seconds):
            raise AssertionError(f"unexpected daemon sleep: {seconds}")

        monkeypatch.setattr(orch, "run_session", fake_run_session)
        monkeypatch.setattr(orchestrator_module.asyncio, "sleep", unexpected_sleep)

        await orch.run()

        assert orch._running is False

    @pytest.mark.asyncio
    async def test_run_session_publishes_idle_status_on_non_trading_day(self):
        """휴장/주말 대기 daemon도 Redis status를 최신 PID/자본으로 갱신한다."""
        from services.trading.orchestrator import (
            HolidayCache,
            TradingConfig,
            TradingOrchestrator,
            TradingState,
        )

        today = date.today()
        holiday_cache = HolidayCache(loader=lambda _: {today})
        orch = TradingOrchestrator(
            TradingConfig.stock(initial_capital=100_000_000),
            holiday_cache=holiday_cache,
        )
        orch._notify = AsyncMock()
        orch._state_publisher = MagicMock()

        await orch.run_session()

        orch._state_publisher.publish_status.assert_called_once()
        status = orch._state_publisher.publish_status.call_args.args[0]
        assert status["state"] == TradingState.IDLE.value
        assert status["config"]["asset_class"] == "stock"
        assert status["config"]["capital"] == 100_000_000

    @pytest.mark.asyncio
    async def test_pause_and_resume(self, monkeypatch):
        """pause/resume 동작"""
        from services.monitoring.metrics import MetricsCollector
        from services.trading.orchestrator import (
            TradingConfig,
            TradingOrchestrator,
            TradingState,
        )

        monkeypatch.setattr(
            MetricsCollector, "start_prometheus_server", lambda *a, **kw: None
        )
        monkeypatch.setattr(
            TradingOrchestrator, "_init_llm_context_publisher", lambda *a, **kw: None
        )

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        await orch.start()
        await orch.pause()
        assert orch.state == TradingState.PAUSED

        await orch.resume()
        assert orch.state == TradingState.RUNNING

        await orch.stop()

    def test_get_status(self):
        """상태 조회"""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        status = orch.get_status()

        assert "state" in status
        assert "config" in status
        assert "stats" in status

    def test_get_status_includes_risk_capital_when_risk_manager_exists(self):
        """Redis status exposes risk-manager capital for operational verification."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.risk.config import RiskConfig
        from shared.risk.manager import RiskManager

        config = TradingConfig.stock(initial_capital=100_000_000)
        orch = TradingOrchestrator(config)
        orch._risk_manager = RiskManager(
            RiskConfig(
                daily_loss_limit_pct=5.0,
                max_total_positions=20,
                initial_capital=100_000_000,
            )
        )

        status = orch.get_status()

        assert status["config"]["capital"] == 100_000_000
        assert status["risk"]["initial_capital"] == 100_000_000.0
        assert status["risk"]["daily_loss_limit_pct"] == 5.0

    def test_get_metrics_without_pipeline(self):
        """파이프라인 없을 때 메트릭 조회"""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        metrics = orch.get_metrics()
        assert metrics == {}

    @pytest.mark.asyncio
    async def test_record_risk_realized_pnl_updates_entry_gate(self):
        """청산 실현손익은 다음 진입 리스크 게이트에 즉시 반영된다."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.risk.config import RiskConfig
        from shared.risk.manager import RiskManager
        from shared.risk.models import BlockReason

        config = TradingConfig.stock(initial_capital=10_000_000)
        orch = TradingOrchestrator(config)
        orch._risk_manager = RiskManager(
            RiskConfig(
                daily_loss_limit_pct=5.0,
                max_total_positions=20,
                initial_capital=10_000_000,
            )
        )
        orch._risk_manager.save_to_redis = AsyncMock()

        await orch._record_risk_realized_pnl(-600_000)

        state = orch._risk_manager.get_risk_state()
        assert state.daily_realized_pnl == -600_000
        assert state.daily_pnl_pct == -6.0
        assert orch._risk_manager.can_open_position("stock") is False
        assert state.block_reason == BlockReason.DAILY_LOSS_LIMIT
        orch._risk_manager.save_to_redis.assert_awaited_once()

    def test_create_pipeline_applies_pipeline_yaml(self, monkeypatch):
        """pipeline.yaml의 스테이지 간격이 TradingPipeline에 반영된다."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from services.trading.pipeline import PipelineStage
        from shared.config.loader import ConfigLoader

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        monkeypatch.setattr(
            ConfigLoader,
            "load",
            staticmethod(
                lambda path, *_args, **_kwargs: (
                    {"pipeline": {"intervals": {"entry": 0.25}}}
                    if path == "pipeline.yaml"
                    else {}
                )
            ),
        )

        pipeline = orch._create_pipeline()
        assert pipeline.intervals[PipelineStage.ENTRY] == 0.25

    def test_record_market_metrics_syncs_open_positions(self):
        """시장 메트릭 기록 시 open positions gauge 동기화."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        orch = TradingOrchestrator(config)
        orch._metrics = MagicMock()
        orch._position_tracker = MagicMock()
        orch._position_tracker.position_count = 1
        orch._indicator_engine = None
        orch._stock_price_feed = None
        orch._futures_price_feed = None
        orch._market_data_snapshot = {}

        orch._record_market_metrics()

        orch._metrics.record_position_change.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_execute_entry_short_direction_uses_sell_and_short_side(self):
        """숏 진입 신호는 SELL 주문 + SHORT 포지션으로 처리."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.models.signal import Signal
        from shared.paper.models import OrderSide as PaperOrderSide

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)

        orch._position_tracker = MagicMock()
        orch._position_tracker.can_open_position.return_value = True
        orch._position_tracker.add_position.return_value = SimpleNamespace(
            id="p1",
            metadata={},
        )
        orch._paper_broker = MagicMock()
        orch._paper_broker.submit_order = AsyncMock(
            return_value=SimpleNamespace(filled=True, fill_price=100.0)
        )
        orch._notify = AsyncMock()
        orch._append_training_trade_event = MagicMock()
        orch._state_publisher = None
        orch._symbol_names = {}

        signal = Signal(
            code="A01603",
            name="KOSPI200 Futures",
            strategy="setup_a_gap_reversion",
            price=100.0,
            confidence=0.8,
            metadata={"signal_direction": "short"},
        )

        await orch._execute_entry(signal)

        submit_kwargs = orch._paper_broker.submit_order.await_args.kwargs
        assert submit_kwargs["side"] == PaperOrderSide.SELL
        add_kwargs = orch._position_tracker.add_position.call_args.kwargs
        assert str(add_kwargs["side"].value) == "short"

    @pytest.mark.asyncio
    async def test_submit_entry_order_blocks_when_spread_wide(self):
        """선물 슬리피지 가드: 스프레드 과도 시 진입 차단."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.execution.slippage_control import (
            FuturesSlippageController,
            SlippageControlConfig,
        )
        from shared.models.signal import Signal

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)
        orch._futures_slippage_controller = FuturesSlippageController(
            SlippageControlConfig.from_dict(
                {
                    "enabled": True,
                    "max_spread_ticks": 1,
                    "tick_size": 0.02,
                    "min_depth_multiplier": 1.0,
                    "cross_asset": {"enabled": False},
                }
            )
        )
        orch._get_quote_payload = AsyncMock(
            return_value={
                "bid_price_1": 330.40,
                "ask_price_1": 330.50,  # 5 ticks
                "bid_qty_1": 10.0,
                "ask_qty_1": 10.0,
                "close": 330.45,
                "timestamp": 1700000000.0,
            }
        )

        signal = Signal(
            code="A05603",
            strategy="setup_a_gap_reversion",
            price=330.45,
            confidence=0.7,
        )

        filled, fill_price, meta = await orch._submit_entry_order(
            code=signal.code,
            is_short=False,
            quantity=1,
            price=signal.price,
            signal=signal,
        )

        assert filled is False
        assert fill_price == 0.0
        assert "wide_spread" in meta["blocked_reason"]

    @pytest.mark.asyncio
    async def test_submit_entry_order_uses_passive_path_when_filters_pass(self):
        """선물 슬리피지 가드: 필터 통과 시 패시브 지정가 경로 사용."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.execution.slippage_control import (
            FuturesSlippageController,
            SlippageControlConfig,
        )
        from shared.models.signal import Signal

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)
        orch._futures_slippage_controller = FuturesSlippageController(
            SlippageControlConfig.from_dict(
                {
                    "enabled": True,
                    "max_spread_ticks": 1,
                    "tick_size": 0.02,
                    "min_depth_multiplier": 1.0,
                    "cross_asset": {"enabled": False},
                    "passive_timeout_seconds": 0.1,
                }
            )
        )
        orch._get_quote_payload = AsyncMock(
            return_value={
                "bid_price_1": 330.48,
                "ask_price_1": 330.50,
                "bid_qty_1": 20.0,
                "ask_qty_1": 20.0,
                "close": 330.49,
                "timestamp": 1700000000.0,
            }
        )
        orch._place_entry_order = AsyncMock(return_value=(True, 330.50, 1, "KRX"))

        signal = Signal(
            code="A05603",
            strategy="setup_a_gap_reversion",
            price=330.50,
            confidence=0.8,
        )

        filled, fill_price, meta = await orch._submit_entry_order(
            code=signal.code,
            is_short=False,
            quantity=1,
            price=signal.price,
            signal=signal,
        )

        assert filled is True
        assert fill_price == 330.50
        assert meta["execution_path"] == "passive_limit"

    @pytest.mark.asyncio
    async def test_submit_entry_order_retries_market_once_after_passive_timeout(self):
        """선물 슬리피지 가드: 패시브 미체결 후 market_once 재시도."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.execution.slippage_control import (
            FuturesSlippageController,
            SlippageControlConfig,
        )
        from shared.models.signal import Signal

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)
        orch._futures_slippage_controller = FuturesSlippageController(
            SlippageControlConfig.from_dict(
                {
                    "enabled": True,
                    "tick_size": 0.02,
                    "max_spread_ticks": 1,
                    "min_depth_multiplier": 1.0,
                    "passive_timeout_seconds": 0.01,
                    "retry_policy": "market_once",
                    "cross_asset": {"enabled": False},
                }
            )
        )
        orch._get_quote_payload = AsyncMock(
            return_value={
                "bid_price_1": 330.48,
                "ask_price_1": 330.50,
                "bid_qty_1": 20.0,
                "ask_qty_1": 20.0,
                "close": 330.49,
                "timestamp": 1700000000.0,
            }
        )
        orch._place_entry_order = AsyncMock(
            side_effect=[
                (False, 0.0, 0, "KRX"),  # passive limit not filled
                (True, 330.50, 1, "KRX"),  # market retry filled
            ]
        )

        signal = Signal(
            code="A05603",
            strategy="setup_a_gap_reversion",
            price=330.49,
            confidence=0.8,
        )

        filled, fill_price, meta = await orch._submit_entry_order(
            code=signal.code,
            is_short=False,
            quantity=1,
            price=signal.price,
            signal=signal,
        )

        assert filled is True
        assert fill_price == 330.50
        assert meta["execution_path"] == "retry_market_once"
        assert orch._place_entry_order.await_count == 2

    @pytest.mark.asyncio
    async def test_submit_entry_order_forwards_signal_timestamp_as_price_source_time(
        self,
    ):
        """Regression: slippage-controlled futures path must forward
        signal.timestamp to _place_entry_order so paper broker's freshness
        guard can validate the price snapshot age. Without this, every entry
        order is rejected with `missing_price_source_time` once signals start
        flowing again (observed after PR #159 + #161 unblocked the entry
        pipeline).
        """
        from datetime import UTC, datetime, timedelta

        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.execution.slippage_control import (
            FuturesSlippageController,
            SlippageControlConfig,
        )
        from shared.models.signal import Signal

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)
        orch._futures_slippage_controller = FuturesSlippageController(
            SlippageControlConfig.from_dict(
                {
                    "enabled": True,
                    "tick_size": 0.02,
                    "max_spread_ticks": 1,
                    "min_depth_multiplier": 1.0,
                    "passive_timeout_seconds": 0.01,
                    "retry_policy": "market_once",
                    "cross_asset": {"enabled": False},
                }
            )
        )
        orch._get_quote_payload = AsyncMock(
            return_value={
                "bid_price_1": 330.48,
                "ask_price_1": 330.50,
                "bid_qty_1": 20.0,
                "ask_qty_1": 20.0,
                "close": 330.49,
                "timestamp": 1700000000.0,
            }
        )
        orch._place_entry_order = AsyncMock(
            side_effect=[
                (False, 0.0, 0, "KRX"),  # passive limit not filled
                (True, 330.50, 1, "KRX"),  # market retry filled
            ]
        )

        # Signal timestamp must be fresh (within
        # SlippageControlConfig.max_signal_age_seconds=2.0); a hard-coded
        # past timestamp made this test time-fragile and broke as soon
        # as the wall clock moved past the deadline.
        signal_ts = datetime.now(UTC) - timedelta(milliseconds=100)
        signal = Signal(
            code="A05603",
            strategy="setup_a_gap_reversion",
            price=330.49,
            confidence=0.8,
            timestamp=signal_ts,
        )

        await orch._submit_entry_order(
            code=signal.code,
            is_short=False,
            quantity=1,
            price=signal.price,
            signal=signal,
        )

        # Both attempts (initial passive + retry market) must forward
        # signal.timestamp as price_source_time.
        assert orch._place_entry_order.await_count == 2
        for call in orch._place_entry_order.await_args_list:
            assert (
                call.kwargs["price_source_time"] == signal_ts
            ), f"price_source_time not forwarded; got {call.kwargs.get('price_source_time')!r}"

    @pytest.mark.asyncio
    async def test_submit_entry_order_does_not_retry_on_partial_fill_signal(self):
        """부분체결 감지 시 재시도 없이 부분 수량만 반영한다."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.execution.slippage_control import (
            FuturesSlippageController,
            SlippageControlConfig,
        )
        from shared.models.signal import Signal

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)
        orch._futures_slippage_controller = FuturesSlippageController(
            SlippageControlConfig.from_dict(
                {
                    "enabled": True,
                    "tick_size": 0.02,
                    "max_spread_ticks": 1,
                    "min_depth_multiplier": 1.0,
                    "passive_timeout_seconds": 0.01,
                    "retry_policy": "market_once",
                    "cross_asset": {"enabled": False},
                }
            )
        )
        orch._get_quote_payload = AsyncMock(
            return_value={
                "bid_price_1": 330.48,
                "ask_price_1": 330.50,
                "bid_qty_1": 20.0,
                "ask_qty_1": 20.0,
                "close": 330.49,
                "timestamp": 1700000000.0,
            }
        )
        orch._place_entry_order = AsyncMock(
            return_value=(True, 330.50, 1, "KRX")  # partial-fill signal from executor
        )

        signal = Signal(
            code="A05603",
            strategy="setup_a_gap_reversion",
            price=330.49,
            confidence=0.8,
        )

        filled, fill_price, meta = await orch._submit_entry_order(
            code=signal.code,
            is_short=False,
            quantity=2,
            price=signal.price,
            signal=signal,
        )

        assert filled is True
        assert fill_price == 330.50
        assert meta["execution_path"] == "passive_limit_partial"
        assert meta["partial_fill"] is True
        assert orch._place_entry_order.await_count == 1

    @pytest.mark.asyncio
    async def test_execute_entry_uses_actual_filled_quantity(self):
        """부분체결 시 요청수량이 아니라 실체결수량으로 포지션을 연다."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.models.signal import Signal

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)

        orch._position_tracker = MagicMock()
        orch._position_tracker.can_open_position.return_value = True
        orch._calculate_quantity = MagicMock(return_value=2)
        orch._submit_entry_order = AsyncMock(
            return_value=(
                True,
                330.50,
                {
                    "mode": "slippage_guard",
                    "filled_qty": 1,
                    "execution_path": "passive_limit_partial",
                },
            )
        )
        orch._process_filled_entry = AsyncMock()

        signal = Signal(
            code="A05603",
            strategy="setup_a_gap_reversion",
            price=330.49,
            confidence=0.8,
        )

        await orch._execute_entry(signal)

        assert orch._process_filled_entry.await_count == 1
        call = orch._process_filled_entry.await_args
        assert call.args[2] == 1

    @pytest.mark.asyncio
    async def test_place_entry_order_futures_limit_needs_fill_confirmation(self):
        """선물 지정가의 접수성공(success=True)만으로 체결 처리하지 않는다."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.execution.models import OrderResponse

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = False
        orch = TradingOrchestrator(config)

        # F-7: the real-execution entry path now requires the live-mode gate to
        # permit it; wire an enabled guard so this test still exercises the real
        # execute_order fill-confirmation logic (not the guard's block path).
        import fakeredis.aioredis

        from shared.execution.live_mode_guard import LiveModeGuard

        orch._live_mode_guard = LiveModeGuard(enabled=True)
        orch._guard_redis = fakeredis.aioredis.FakeRedis(db=1)

        orch._order_executor = MagicMock()
        orch._order_executor.execute_order = AsyncMock(
            return_value=OrderResponse(
                success=True, order_no="00001234", message="accepted"
            )
        )

        filled, fill_price, filled_qty, venue = await orch._place_entry_order(
            code="A05603",
            is_short=False,
            quantity=2,
            order_type="limit",
            limit_price=330.50,
            market_price=330.50,
        )

        assert filled is False
        assert fill_price == 0.0
        assert filled_qty == 0
        assert venue == "KRX"

    @pytest.mark.asyncio
    async def test_place_entry_order_tracks_partial_fill_even_on_cancel(self):
        """타임아웃 후 취소 응답(success=False)이어도 부분체결 수량은 반영한다."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.execution.models import OrderResponse

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = False
        orch = TradingOrchestrator(config)

        # F-7: the real-execution entry path now requires the live-mode gate to
        # permit it (futures_live.enabled + not suspended). Construction here
        # bypasses _init_execution_layer, so wire an enabled guard explicitly.
        import fakeredis.aioredis

        from shared.execution.live_mode_guard import LiveModeGuard

        orch._live_mode_guard = LiveModeGuard(enabled=True)
        orch._guard_redis = fakeredis.aioredis.FakeRedis(db=1)

        orch._order_executor = MagicMock()
        orch._order_executor.execute_order = AsyncMock(
            return_value=OrderResponse(
                success=False,
                order_no="00001234",
                message="timeout_cancelled",
                filled_qty=1,
                filled_price=330.52,
            )
        )

        filled, fill_price, filled_qty, venue = await orch._place_entry_order(
            code="A05603",
            is_short=False,
            quantity=2,
            order_type="limit",
            limit_price=330.50,
            market_price=330.50,
        )

        assert filled is True
        assert fill_price == 330.52
        assert filled_qty == 1
        assert venue == "KRX"

    @pytest.mark.asyncio
    async def test_execute_exit_short_position_uses_buy(self):
        """숏 포지션 청산은 BUY 주문으로 처리."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.models.position import PositionSide
        from shared.models.signal import ExitReason, ExitSignal
        from shared.paper.models import OrderSide as PaperOrderSide

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)

        position = SimpleNamespace(
            id="p1",
            side=PositionSide.SHORT,
            quantity=2,
            metadata={},
            name="KOSPI200 Futures",
            unrealized_pnl=0.0,
            profit_pct=0.0,
            exit_time=None,
            entry_time=None,
            entry_price=100.0,
        )
        orch._position_tracker = MagicMock()
        orch._position_tracker.get_position.return_value = position
        orch._position_tracker.close_position.return_value = position
        orch._paper_broker = MagicMock()
        orch._paper_broker.submit_order = AsyncMock(
            return_value=SimpleNamespace(filled=True, fill_price=99.0)
        )
        orch._notify = AsyncMock()
        orch._append_training_trade_event = MagicMock()
        orch._state_publisher = None
        orch._symbol_names = {}

        signal = ExitSignal(
            code="A01603",
            position_id="p1",
            reason=ExitReason.MANUAL_CLOSE,
            strategy="three_stage",
            exit_price=99.0,
            quantity=0,
        )
        await orch._execute_exit(signal)

        submit_kwargs = orch._paper_broker.submit_order.await_args.kwargs
        assert submit_kwargs["side"] == PaperOrderSide.BUY
        assert submit_kwargs["quantity"] == 2

    @pytest.mark.asyncio
    async def test_verify_positions_skips_futures_paper_broker_check(self, monkeypatch):
        """선물 paper 모드에서는 브로커 잔고검증 API를 호출하지 않는다."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.config.loader import ConfigLoader

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)

        orch._kis_client = MagicMock()
        orch._kis_client.config = MagicMock()
        orch._kis_client.config.is_real = True
        orch._kis_client.get_futures_balance = AsyncMock(return_value=[])

        monkeypatch.setattr(
            ConfigLoader,
            "load",
            staticmethod(
                lambda *_args, **_kwargs: {"broker_verification": {"enabled": True}}
            ),
        )

        await orch._verify_positions_with_broker()

        orch._kis_client.get_futures_balance.assert_not_called()


class TestDefaultHolidayLoader:
    """default_holiday_loader 함수 테스트"""

    def test_returns_empty_set_when_file_not_found(self):
        """파일 없으면 빈 set 반환"""
        from services.trading.orchestrator import default_holiday_loader

        holidays = default_holiday_loader("nonexistent.yaml")
        assert holidays == set()

    def test_loads_holidays_from_config(self):
        """설정 파일에서 공휴일 로드"""
        import os
        import tempfile

        from services.trading.orchestrator import default_holiday_loader

        content = """
holidays:
  - "2024-01-01"
  - "2024-03-01"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            holidays = default_holiday_loader(temp_path)
            assert date(2024, 1, 1) in holidays
            assert date(2024, 3, 1) in holidays
        finally:
            os.unlink(temp_path)


class TestHolidayCache:
    """HolidayCache 클래스 테스트"""

    def test_get_returns_holidays(self):
        """get()은 공휴일 반환"""
        from services.trading.orchestrator import HolidayCache

        test_holidays = {date(2024, 1, 1)}
        cache = HolidayCache(loader=lambda _: test_holidays)

        result = cache.get()
        assert result == test_holidays

    def test_reload_clears_cache(self):
        """reload()는 캐시 클리어"""
        from services.trading.orchestrator import HolidayCache

        call_count = [0]

        def counting_loader(_):
            call_count[0] += 1
            return {date(2024, 1, 1)}

        cache = HolidayCache(loader=counting_loader)

        # First call
        cache.get()
        assert call_count[0] == 1

        # Second call uses cache
        cache.get()
        assert call_count[0] == 1

        # Reload and call again
        cache.reload()
        cache.get()
        assert call_count[0] == 2


class TestReloadHolidays:
    """reload_holidays 함수 테스트"""

    def test_reloads_global_cache(self):
        """전역 캐시 리로드"""
        from services.trading import orchestrator

        # Get initial holidays
        _ = orchestrator._get_holidays()

        # Reload
        orchestrator.reload_holidays()

        # Can get holidays again (may or may not be same)
        holidays2 = orchestrator._get_holidays()

        # Should still work
        assert isinstance(holidays2, set)


class TestMarketClassification:
    """TradingOrchestrator._classify_market 테스트"""

    @staticmethod
    def _fallback_config():
        from services.trading.orchestrator import TradingConfig

        return TradingConfig.stock(
            symbols=["005930", "000660"],
            regime_require_daily_indicators=False,
            regime_require_mfi_symbols=False,
        )

    def test_bull_market(self):
        """상승장 (BULL) 감지"""
        from services.trading.orchestrator import TradingOrchestrator

        config = self._fallback_config()
        orch = TradingOrchestrator(config)

        # Average change > 2% = BULL
        data = {
            "005930": {"change": 0.03},  # +3%
            "000660": {"change": 0.025},  # +2.5%
        }
        assert orch._classify_market(data) == "BULL"

    def test_bear_market(self):
        """하락장 (BEAR) 감지"""
        from services.trading.orchestrator import TradingOrchestrator

        config = self._fallback_config()
        orch = TradingOrchestrator(config)

        # Average change < -2% = BEAR
        data = {
            "005930": {"change": -0.03},  # -3%
            "000660": {"change": -0.025},  # -2.5%
        }
        assert orch._classify_market(data) == "BEAR"

    def test_sideways_up(self):
        """소폭 상승 횡보장 감지"""
        from services.trading.orchestrator import TradingOrchestrator

        config = self._fallback_config()
        orch = TradingOrchestrator(config)

        # 0 < change <= 2% = SIDEWAYS_UP
        data = {
            "005930": {"change": 0.01},  # +1%
            "000660": {"change": 0.005},  # +0.5%
        }
        assert orch._classify_market(data) == "SIDEWAYS_UP"

    def test_sideways_down(self):
        """소폭 하락 횡보장 감지"""
        from services.trading.orchestrator import TradingOrchestrator

        config = self._fallback_config()
        orch = TradingOrchestrator(config)

        # -2% <= change < 0 = SIDEWAYS_DOWN
        data = {
            "005930": {"change": -0.01},  # -1%
            "000660": {"change": -0.005},  # -0.5%
        }
        assert orch._classify_market(data) == "SIDEWAYS_DOWN"

    def test_sideways_flat(self):
        """변화 없음"""
        from services.trading.orchestrator import TradingOrchestrator

        config = self._fallback_config()
        orch = TradingOrchestrator(config)

        # Zero change = SIDEWAYS_FLAT
        data = {
            "005930": {"change": 0},
            "000660": {"change": 0},
        }
        assert orch._classify_market(data) == "SIDEWAYS_FLAT"

    def test_empty_data(self):
        """빈 데이터"""
        from services.trading.orchestrator import TradingOrchestrator

        config = self._fallback_config()
        orch = TradingOrchestrator(config)

        assert orch._classify_market({}) == "UNKNOWN"

    def test_no_change_field(self):
        """change 필드 없음"""
        from services.trading.orchestrator import TradingOrchestrator

        config = self._fallback_config()
        orch = TradingOrchestrator(config)

        data = {
            "005930": {"close": 71000},  # no change field
            "000660": {"close": 80000},
        }
        assert orch._classify_market(data) == "SIDEWAYS_FLAT"

    def test_thresholds_are_constants(self):
        """threshold는 클래스 상수로 정의"""
        from services.trading.orchestrator import TradingOrchestrator

        # Verify thresholds are defined as class constants
        assert hasattr(TradingOrchestrator, "MARKET_BULL_THRESHOLD")
        assert hasattr(TradingOrchestrator, "MARKET_BEAR_THRESHOLD")
        assert TradingOrchestrator.MARKET_BULL_THRESHOLD == 0.02
        assert TradingOrchestrator.MARKET_BEAR_THRESHOLD == -0.02


class TestQuantitySizing:
    """Order quantity sizing tests."""

    def test_strategy_sizer_receives_strategy_scoped_positions(self):
        """Strategy max_positions should not be tripped by other strategies."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.strategy.position.sizers import FixedSizerConfig

        orch = TradingOrchestrator.__new__(TradingOrchestrator)
        orch.config = TradingConfig.stock(initial_capital=100_000_000)
        orch._paper_broker = None
        orch._adaptive_sizing = None

        strategy = MagicMock()
        strategy.position_sizer.config = FixedSizerConfig(
            fixed_amount=750_000,
            max_positions=4,
        )
        strategy.calculate_position_size.return_value = 7

        orch._strategy_manager = SimpleNamespace(strategies={"vr_composite": strategy})
        other_positions = [
            SimpleNamespace(strategy="daily_pullback"),
            SimpleNamespace(strategy="daily_pullback"),
            SimpleNamespace(strategy="daily_pullback"),
            SimpleNamespace(strategy="daily_pullback"),
            SimpleNamespace(strategy="daily_pullback"),
        ]
        orch._position_tracker = SimpleNamespace(
            positions=other_positions,
            get_positions_by_strategy=MagicMock(return_value=[]),
        )

        signal = SimpleNamespace(
            code="055550",
            price=95_100.0,
            quantity=0,
            strategy="vr_composite",
        )

        assert orch._calculate_quantity(signal) == 7
        strategy.calculate_position_size.assert_called_once()
        assert (
            strategy.calculate_position_size.call_args.kwargs["current_positions"] == []
        )


class TestStaticUniverse:
    """Static universe mode tests"""

    def test_universe_mode_default(self):
        """Default universe_mode is 'dynamic'"""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig.stock()
        assert config.universe_mode == "dynamic"

    def test_universe_mode_static(self):
        """Can set universe_mode to 'static'"""
        from services.trading.orchestrator import TradingConfig

        config = TradingConfig(asset_class="stock", universe_mode="static")
        assert config.universe_mode == "static"

    def test_universe_mode_invalid(self):
        """Invalid universe_mode raises ValueError"""
        from services.trading.orchestrator import TradingConfig

        with pytest.raises(ValueError, match="universe_mode"):
            TradingConfig(asset_class="stock", universe_mode="invalid")

    def test_daily_watchlist_init(self):
        """Orchestrator initializes _daily_watchlist as empty dict"""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)
        assert orch._daily_watchlist == {}
        assert orch._daily_watchlist_key == "system:daily_watchlist:latest"

    def test_load_static_watchlist_success(self, monkeypatch):
        """_load_static_watchlist loads symbols from Redis"""
        import json

        import shared.streaming.client
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        config = TradingConfig(asset_class="stock", universe_mode="static")
        orch = TradingOrchestrator(config)

        watchlist_data = {
            "strategies": {
                "trend_pullback": ["005930", "000660"],
                "momentum_breakout": ["035720"],
            },
            "scanned_at": "2026-02-26T08:30:00",
        }
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(watchlist_data)

        monkeypatch.setattr(
            shared.streaming.client.RedisClient,
            "get_client",
            staticmethod(lambda: mock_redis),
        )
        monkeypatch.setattr(
            TradingOrchestrator, "_hydrate_missing_symbol_names", lambda *_: None
        )

        result = orch._load_static_watchlist()
        assert result is True
        assert set(orch.config.symbols) == {"005930", "000660", "035720"}
        assert orch._daily_watchlist == watchlist_data
        assert "strategies" in orch._daily_watchlist

    def test_load_static_watchlist_no_data(self, monkeypatch):
        """_load_static_watchlist returns False when Redis key missing"""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        config = TradingConfig(asset_class="stock", universe_mode="static")
        orch = TradingOrchestrator(config)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        import shared.streaming.client

        monkeypatch.setattr(
            shared.streaming.client.RedisClient, "get_client", lambda: mock_redis
        )
        monkeypatch.setattr(
            TradingOrchestrator, "_hydrate_missing_symbol_names", lambda *_: None
        )

        result = orch._load_static_watchlist()
        assert result is False

    def test_load_static_watchlist_empty_strategies(self, monkeypatch):
        """_load_static_watchlist returns False when strategies are empty"""
        import json

        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        config = TradingConfig(asset_class="stock", universe_mode="static")
        orch = TradingOrchestrator(config)

        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"strategies": {}})

        import shared.streaming.client

        monkeypatch.setattr(
            shared.streaming.client.RedisClient, "get_client", lambda: mock_redis
        )
        monkeypatch.setattr(
            TradingOrchestrator, "_hydrate_missing_symbol_names", lambda *_: None
        )

        result = orch._load_static_watchlist()
        assert result is False

    def test_hydrate_missing_symbol_names_uses_krx_open_api_map(self, monkeypatch):
        """Missing stock names are hydrated from KRX Open API map."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        config = TradingConfig(asset_class="stock")
        orch = TradingOrchestrator(config)

        monkeypatch.setattr(
            orch,
            "_load_krx_open_api_symbol_names",
            lambda: {
                "005930": "삼성전자",
                "000660": "SK하이닉스",
            },
        )

        orch._hydrate_missing_symbol_names({"005930", "000660", "035720"})

        assert orch._symbol_names["005930"] == "삼성전자"
        assert orch._symbol_names["000660"] == "SK하이닉스"
        assert "035720" in orch._symbol_name_lookup_attempted
        assert orch._symbol_metadata_cache["005930"]["name"] == "삼성전자"


class TestOrderLatencyActivation:
    """Bottleneck observability: the execute path records real submit latency."""

    @pytest.mark.asyncio
    async def test_execute_entry_records_positive_order_latency(self):
        """_execute_entry brackets the submit, records order latency, threads it on."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.models.signal import Signal

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)

        orch._metrics = MagicMock()
        orch._position_tracker = MagicMock()
        orch._position_tracker.can_open_position.return_value = True
        orch._calculate_quantity = MagicMock(return_value=2)
        orch._submit_entry_order = AsyncMock(
            return_value=(True, 330.50, {"filled_qty": 2})
        )
        orch._process_filled_entry = AsyncMock()

        signal = Signal(
            code="A05603",
            strategy="setup_a_gap_reversion",
            price=330.49,
            confidence=0.8,
        )

        await orch._execute_entry(signal)

        # record_order_latency called once with a non-negative latency
        assert orch._metrics.record_order_latency.call_count == 1
        latency_arg = orch._metrics.record_order_latency.call_args.args[0]
        assert latency_arg >= 0.0

        # latency threaded into _process_filled_entry as order_latency_ms
        call = orch._process_filled_entry.await_args
        assert call.kwargs["order_latency_ms"] == latency_arg

    @pytest.mark.asyncio
    async def test_execute_exit_records_positive_order_latency(self):
        """_execute_exit brackets the submit and records order latency."""
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator
        from shared.models.position import PositionSide

        config = TradingConfig.futures(strategy_name="setup_a_gap_reversion")
        config.paper_trading = True
        orch = TradingOrchestrator(config)

        orch._metrics = MagicMock()
        orch._position_tracker = MagicMock()
        orch._position_tracker.get_position.return_value = SimpleNamespace(
            side=PositionSide.LONG,
            quantity=2,
        )
        orch._submit_exit_order = AsyncMock(return_value=(True, 331.0))
        orch._process_filled_exit = AsyncMock()

        signal = SimpleNamespace(
            code="A05603",
            position_id="pos-1",
            quantity=2,
            exit_price=331.0,
        )

        await orch._execute_exit(signal)

        assert orch._metrics.record_order_latency.call_count == 1
        latency_arg = orch._metrics.record_order_latency.call_args.args[0]
        assert latency_arg >= 0.0
        assert orch._process_filled_exit.await_count == 1
