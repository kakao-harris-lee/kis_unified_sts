"""Shared entry gate helpers for strategy session and cooldown checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class MarketSessionWindow:
    market_open_hour: int
    market_open_minute: int
    market_close_hour: int
    market_close_minute: int
    skip_market_open_minutes: int = 0
    skip_market_close_minutes: int = 0


def _to_kst(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=KST)
    return timestamp.astimezone(KST)


def is_in_entry_session(timestamp: datetime, window: MarketSessionWindow) -> bool:
    """Return whether ``timestamp`` passes same-day KST entry-session guards.

    This helper intentionally mirrors the existing strategy gates: the market
    close time is only enforced when ``skip_market_close_minutes`` is positive.
    A zero close buffer does not add a new exact-close cutoff.
    """
    timestamp_kst = _to_kst(timestamp)
    open_dt = datetime.combine(
        timestamp_kst.date(),
        time(window.market_open_hour, window.market_open_minute),
        tzinfo=KST,
    )
    close_dt = datetime.combine(
        timestamp_kst.date(),
        time(window.market_close_hour, window.market_close_minute),
        tzinfo=KST,
    )

    if timestamp_kst < open_dt:
        return False
    if window.skip_market_open_minutes > 0 and timestamp_kst < open_dt + timedelta(
        minutes=window.skip_market_open_minutes
    ):
        return False
    if window.skip_market_close_minutes > 0:
        if timestamp_kst >= close_dt - timedelta(
            minutes=window.skip_market_close_minutes
        ):
            return False
    return True


def cooldown_elapsed(
    now: datetime,
    last_signal_at: datetime | None,
    cooldown_seconds: float,
) -> bool:
    """Return whether a signal cooldown has elapsed."""
    if cooldown_seconds <= 0 or last_signal_at is None:
        return True

    elapsed_seconds = (_to_kst(now) - _to_kst(last_signal_at)).total_seconds()
    return elapsed_seconds >= cooldown_seconds
