"""Trading Orchestrator 테스트"""

import pytest
from datetime import date, time
from unittest.mock import MagicMock, patch, AsyncMock


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
        """기본 선물 거래 시간"""
        from services.trading.orchestrator import MarketSchedule

        schedule = MarketSchedule()
        assert schedule.futures_open == time(9, 0)
        assert schedule.futures_close == time(15, 45)

    def test_get_open_time(self):
        """개장 시간 조회"""
        from services.trading.orchestrator import MarketSchedule

        schedule = MarketSchedule()
        assert schedule.get_open_time("stock") == time(9, 0)
        assert schedule.get_open_time("futures") == time(9, 0)

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


class TestTradingOrchestrator:
    """TradingOrchestrator 클래스 테스트"""

    def test_init(self):
        """초기화"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig, TradingState

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        assert orch.state == TradingState.IDLE
        assert orch.session_count == 0
        assert orch.total_trades == 0

    def test_is_running_when_idle(self):
        """IDLE 상태에서 is_running"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        assert orch.is_running is False

    @pytest.mark.asyncio
    async def test_start_changes_state(self):
        """start() 호출 시 상태 변경"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig, TradingState

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        await orch.start()
        assert orch.state == TradingState.RUNNING

        await orch.stop()

    @pytest.mark.asyncio
    async def test_stop_changes_state(self):
        """stop() 호출 시 상태 변경"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig, TradingState

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        await orch.start()
        await orch.stop()

        assert orch.state == TradingState.STOPPED

    @pytest.mark.asyncio
    async def test_pause_and_resume(self):
        """pause/resume 동작"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig, TradingState

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
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        status = orch.get_status()

        assert "state" in status
        assert "config" in status
        assert "stats" in status

    def test_get_metrics_without_pipeline(self):
        """파이프라인 없을 때 메트릭 조회"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        metrics = orch.get_metrics()
        assert metrics == {}


class TestLoadHolidaysFromConfig:
    """_load_holidays_from_config 함수 테스트"""

    def test_returns_empty_set_when_file_not_found(self):
        """파일 없으면 빈 set 반환"""
        from services.trading.orchestrator import _load_holidays_from_config

        holidays = _load_holidays_from_config("nonexistent.yaml")
        assert holidays == set()

    def test_loads_holidays_from_config(self):
        """설정 파일에서 공휴일 로드"""
        from services.trading.orchestrator import _load_holidays_from_config
        import tempfile
        import os

        content = """
holidays:
  - "2024-01-01"
  - "2024-03-01"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            holidays = _load_holidays_from_config(temp_path)
            assert date(2024, 1, 1) in holidays
            assert date(2024, 3, 1) in holidays
        finally:
            os.unlink(temp_path)


class TestReloadHolidays:
    """reload_holidays 함수 테스트"""

    def test_clears_cache(self):
        """캐시 클리어"""
        from services.trading import orchestrator

        # 캐시 설정
        orchestrator._cached_holidays = {date(2024, 1, 1)}

        orchestrator.reload_holidays()

        assert orchestrator._cached_holidays is None
