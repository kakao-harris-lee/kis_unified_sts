"""Session calendar extraction tests."""

from __future__ import annotations

from datetime import date, time

from services.trading import orchestrator, session_calendar
from services.trading.session_calendar import (
    HolidayCache,
    HolidayLoader,
    MarketSchedule,
    TradingState,
    default_holiday_loader,
    is_trading_day,
    reload_holidays,
    set_holiday_cache,
)


def test_market_schedule_defaults_match_orchestrator_contract() -> None:
    schedule = MarketSchedule()

    assert schedule.get_open_time("stock") == time(9, 0)
    assert schedule.get_close_time("stock") == time(15, 30)
    assert schedule.get_open_time("futures") == time(8, 45)
    assert schedule.get_close_time("futures") == time(15, 45)


def test_market_schedule_loads_regular_hours_from_yaml(tmp_path) -> None:
    config_path = tmp_path / "market_schedule.yaml"
    config_path.write_text(
        """
market_schedule:
  stock:
    regular:
      open: "09:01"
      close: "15:31"
  futures:
    regular:
      open: "08:46"
      close: "15:46"
""",
        encoding="utf-8",
    )

    schedule = MarketSchedule.load_from_yaml(str(config_path))

    assert schedule.get_open_time("stock") == time(9, 1)
    assert schedule.get_close_time("stock") == time(15, 31)
    assert schedule.get_open_time("futures") == time(8, 46)
    assert schedule.get_close_time("futures") == time(15, 46)


def test_is_trading_day_respects_weekends_and_explicit_holidays() -> None:
    assert is_trading_day(date(2026, 7, 6), holidays=set()) is True
    assert is_trading_day(date(2026, 7, 4), holidays=set()) is False
    assert (
        is_trading_day(
            date(2026, 7, 6),
            holidays={date(2026, 7, 6)},
        )
        is False
    )


def test_holiday_cache_invalidates_until_next_get_on_reload() -> None:
    calls = 0

    def loader(config_path: str) -> set[date]:
        nonlocal calls
        calls += 1
        assert config_path == "custom.yaml"
        return {date(2026, 1, 1)}

    cache = HolidayCache(loader=loader, config_path="custom.yaml")

    assert cache.get() == {date(2026, 1, 1)}
    assert cache.get() == {date(2026, 1, 1)}
    assert calls == 1

    cache.reload()

    assert calls == 1
    assert cache.get() == {date(2026, 1, 1)}
    assert calls == 2


def test_orchestrator_global_holiday_cache_compatibility() -> None:
    original_cache = session_calendar._holiday_cache
    custom_cache = HolidayCache(loader=lambda _: {date(2026, 3, 2)})
    try:
        set_holiday_cache(custom_cache)

        assert orchestrator._get_holidays() == {date(2026, 3, 2)}

        runtime = orchestrator.TradingOrchestrator(orchestrator.TradingConfig.stock())

        assert runtime._holiday_cache is custom_cache
    finally:
        set_holiday_cache(original_cache)


def test_orchestrator_reexports_session_calendar_symbols() -> None:
    assert orchestrator.MarketSchedule is MarketSchedule
    assert orchestrator.HolidayCache is HolidayCache
    assert orchestrator.HolidayLoader is HolidayLoader
    assert orchestrator.TradingState is TradingState
    assert orchestrator.default_holiday_loader is default_holiday_loader
    assert orchestrator.is_trading_day is is_trading_day
    assert orchestrator.reload_holidays is reload_holidays
    assert orchestrator.set_holiday_cache is set_holiday_cache
