"""Test legacy market-data models."""

from datetime import date, datetime


def test_daily_candle_creation():
    """Test DailyCandle dataclass creation."""
    from shared.db.models import DailyCandle

    candle = DailyCandle(
        code="005930",
        date=date(2025, 1, 15),
        open=58000.0,
        high=59000.0,
        low=57500.0,
        close=58500.0,
        volume=1000000,
        value=58500000000,
        change_rate=0.86,
    )

    assert candle.code == "005930"
    assert candle.close == 58500.0
    assert candle.change_rate == 0.86


def test_minute_candle_creation():
    """Test MinuteCandle dataclass creation."""
    from shared.db.models import MinuteCandle

    candle = MinuteCandle(
        code="005930",
        datetime=datetime(2025, 1, 15, 9, 30),
        open=58000.0,
        high=58100.0,
        low=57900.0,
        close=58050.0,
        volume=5000,
        value=290250000,
    )

    assert candle.code == "005930"
    assert candle.datetime.hour == 9
    assert candle.datetime.minute == 30


def test_tick_data_creation():
    """Test TickData dataclass creation."""
    from shared.db.models import TickData

    tick = TickData(
        code="005930",
        datetime=datetime(2025, 1, 15, 9, 30, 15, 123000),
        price=58000.0,
        volume=100,
        bid_price=57990.0,
        ask_price=58010.0,
        cumulative_volume=50000,
    )

    assert tick.price == 58000.0
    assert tick.bid_price == 57990.0
