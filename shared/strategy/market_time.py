"""Shared market-time helpers for strategy runtime."""

from __future__ import annotations

from datetime import datetime, time

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo

from shared.calendar import get_market_calendar

KST = ZoneInfo("Asia/Seoul")


def to_kst(dt: datetime) -> datetime:
    """Normalize datetime to Asia/Seoul timezone."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def now_kst() -> datetime:
    """Current time in KST."""
    return datetime.now(KST)


def is_trading_day_kst(dt: datetime) -> bool:
    """Check trading day using KRX calendar."""
    calendar = get_market_calendar()
    return calendar.is_market_day(to_kst(dt).date())


def calendar_close_time() -> time:
    """KRX regular close time from calendar."""
    calendar = get_market_calendar()
    return calendar.MARKET_CLOSE_TIME


def effective_close_time(config_close: time | None = None) -> time:
    """Return close cutoff time bounded by exchange close."""
    market_close = calendar_close_time()
    if config_close is None:
        return market_close
    return config_close if config_close <= market_close else market_close
