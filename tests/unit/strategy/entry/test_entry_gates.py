"""Tests for shared entry-session and cooldown gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from shared.strategy.entry.gates import (
    MarketSessionWindow,
    cooldown_elapsed,
    is_in_entry_session,
)

KST = ZoneInfo("Asia/Seoul")


def _window(**overrides) -> MarketSessionWindow:
    defaults = {
        "market_open_hour": 9,
        "market_open_minute": 0,
        "market_close_hour": 15,
        "market_close_minute": 15,
    }
    defaults.update(overrides)
    return MarketSessionWindow(**defaults)


def _kst(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 25, hour, minute, tzinfo=KST)


def _naive(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 25, hour, minute)


def test_cooldown_elapsed_returns_true_without_last_signal() -> None:
    assert (
        cooldown_elapsed(
            now=_kst(10, 0),
            last_signal_at=None,
            cooldown_seconds=300,
        )
        is True
    )


def test_cooldown_elapsed_accepts_positional_arguments() -> None:
    assert cooldown_elapsed(_kst(10, 5), _kst(10, 0), 300) is True


def test_cooldown_elapsed_blocks_before_cooldown_seconds_elapsed() -> None:
    now = _kst(10, 4)
    last_signal_at = _kst(10, 0)

    assert (
        cooldown_elapsed(
            now=now,
            last_signal_at=last_signal_at,
            cooldown_seconds=300,
        )
        is False
    )


def test_cooldown_elapsed_allows_at_and_after_cooldown_seconds() -> None:
    last_signal_at = _kst(10, 0)

    assert (
        cooldown_elapsed(
            now=last_signal_at + timedelta(seconds=300),
            last_signal_at=last_signal_at,
            cooldown_seconds=300,
        )
        is True
    )
    assert (
        cooldown_elapsed(
            now=last_signal_at + timedelta(seconds=301),
            last_signal_at=last_signal_at,
            cooldown_seconds=300,
        )
        is True
    )


def test_cooldown_elapsed_treats_naive_timestamps_as_kst() -> None:
    assert cooldown_elapsed(_kst(10, 5), _naive(10, 0), 300) is True
    assert cooldown_elapsed(_naive(10, 4), _kst(10, 0), 300) is False


def test_cooldown_elapsed_allows_when_cooldown_is_disabled() -> None:
    assert (
        cooldown_elapsed(
            now=_kst(10, 1),
            last_signal_at=_kst(10, 0),
            cooldown_seconds=0,
        )
        is True
    )


def test_is_in_entry_session_blocks_before_market_open() -> None:
    assert is_in_entry_session(_kst(8, 59), _window()) is False


def test_is_in_entry_session_blocks_inside_skip_market_open_minutes() -> None:
    window = _window(skip_market_open_minutes=30)

    assert is_in_entry_session(_kst(9, 29), window) is False


def test_is_in_entry_session_allows_during_active_session() -> None:
    window = _window(
        skip_market_open_minutes=30,
        skip_market_close_minutes=15,
    )

    assert is_in_entry_session(_kst(9, 30), window) is True
    assert (
        is_in_entry_session(datetime(2026, 6, 25, 1, 0, tzinfo=UTC), window)
        is True
    )


def test_is_in_entry_session_treats_naive_timestamp_as_kst() -> None:
    window = _window(skip_market_open_minutes=30, skip_market_close_minutes=15)

    assert is_in_entry_session(_naive(9, 30), window) is True


def test_is_in_entry_session_blocks_inside_skip_market_close_minutes() -> None:
    window = _window(skip_market_close_minutes=15)

    assert is_in_entry_session(_kst(14, 59), window) is True
    assert is_in_entry_session(_kst(15, 0), window) is False


def test_is_in_entry_session_zero_close_buffer_does_not_add_close_cutoff() -> None:
    window = _window(skip_market_close_minutes=0)

    assert is_in_entry_session(_kst(15, 15), window) is True
    assert is_in_entry_session(_kst(16, 0), window) is True
