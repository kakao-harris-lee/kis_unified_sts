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


class TestDefaultHolidayLoader:
    """default_holiday_loader 함수 테스트"""

    def test_returns_empty_set_when_file_not_found(self):
        """파일 없으면 빈 set 반환"""
        from services.trading.orchestrator import default_holiday_loader

        holidays = default_holiday_loader("nonexistent.yaml")
        assert holidays == set()

    def test_loads_holidays_from_config(self):
        """설정 파일에서 공휴일 로드"""
        from services.trading.orchestrator import default_holiday_loader
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
        holidays1 = orchestrator._get_holidays()

        # Reload
        orchestrator.reload_holidays()

        # Can get holidays again (may or may not be same)
        holidays2 = orchestrator._get_holidays()

        # Should still work
        assert isinstance(holidays2, set)


class TestMarketClassification:
    """TradingOrchestrator._classify_market 테스트"""

    def test_bull_market(self):
        """상승장 (BULL) 감지"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        # Average change > 2% = BULL
        data = {
            "005930": {"change": 0.03},  # +3%
            "000660": {"change": 0.025},  # +2.5%
        }
        assert orch._classify_market(data) == "BULL"

    def test_bear_market(self):
        """하락장 (BEAR) 감지"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        # Average change < -2% = BEAR
        data = {
            "005930": {"change": -0.03},  # -3%
            "000660": {"change": -0.025},  # -2.5%
        }
        assert orch._classify_market(data) == "BEAR"

    def test_sideways_up(self):
        """소폭 상승 횡보장 감지"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        # 0 < change <= 2% = SIDEWAYS_UP
        data = {
            "005930": {"change": 0.01},  # +1%
            "000660": {"change": 0.005},  # +0.5%
        }
        assert orch._classify_market(data) == "SIDEWAYS_UP"

    def test_sideways_down(self):
        """소폭 하락 횡보장 감지"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        # -2% <= change < 0 = SIDEWAYS_DOWN
        data = {
            "005930": {"change": -0.01},  # -1%
            "000660": {"change": -0.005},  # -0.5%
        }
        assert orch._classify_market(data) == "SIDEWAYS_DOWN"

    def test_sideways_flat(self):
        """변화 없음"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        # Zero change = SIDEWAYS_FLAT
        data = {
            "005930": {"change": 0},
            "000660": {"change": 0},
        }
        assert orch._classify_market(data) == "SIDEWAYS_FLAT"

    def test_empty_data(self):
        """빈 데이터"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
        orch = TradingOrchestrator(config)

        assert orch._classify_market({}) == "UNKNOWN"

    def test_no_change_field(self):
        """change 필드 없음"""
        from services.trading.orchestrator import TradingOrchestrator, TradingConfig

        config = TradingConfig.stock()
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
