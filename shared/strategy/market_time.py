"""Shared market-time helpers for strategy runtime."""

from __future__ import annotations

import logging
from datetime import datetime, time

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo

from shared.calendar import get_market_calendar

logger = logging.getLogger(__name__)

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


def is_futures_night_session_enabled() -> bool:
    """Read ``config/market_schedule.yaml::futures.night.enabled`` (default False).

    Fail-closed: any read or parse error returns False so the order_router /
    executor refuses to place futures orders during the night-session window
    until config is repaired. The legal-review runbook
    (``docs/runbooks/futures-legal-review.md`` §4) requires this flag to be
    explicitly ``false`` until the operator completes the night-session
    compliance review.
    """
    try:
        from shared.config.loader import ConfigLoader

        data = ConfigLoader.load("market_schedule.yaml")
    except Exception:
        logger.warning(
            "market_schedule.yaml load failed; treating futures night session as disabled"
        )
        return False
    if not isinstance(data, dict):
        return False
    night = (
        data.get("market_schedule", {}).get("futures", {}).get("night", {}) or {}
    )
    if not isinstance(night, dict):
        return False
    return bool(night.get("enabled", False))
