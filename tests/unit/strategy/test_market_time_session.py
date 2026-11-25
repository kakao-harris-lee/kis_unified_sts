"""Tests for is_regular_session_open (producer market-hours gate)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from shared.strategy.market_time import is_regular_session_open

_KST = ZoneInfo("Asia/Seoul")


def _kst(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=_KST)


def test_open_during_weekday_session():
    assert is_regular_session_open(_kst(2026, 6, 9, 11, 0)) is True
    assert is_regular_session_open(_kst(2026, 6, 9, 9, 0)) is True


def test_closed_outside_session_hours():
    assert is_regular_session_open(_kst(2026, 6, 9, 8, 30)) is False
    assert is_regular_session_open(_kst(2026, 6, 9, 16, 30)) is False


def test_closed_on_weekend():
    assert is_regular_session_open(_kst(2026, 6, 6, 11, 0)) is False
    assert is_regular_session_open(_kst(2026, 6, 7, 11, 0)) is False
