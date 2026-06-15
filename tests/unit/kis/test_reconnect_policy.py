"""Tests for the KIS reconnect circuit-breaker policy."""

from __future__ import annotations

import pytest

from shared.kis.reconnect_policy import ReconnectPolicy


def _policy(**kw):
    defaults = {
        "initial_delay": 1.0,
        "max_delay": 60.0,
        "breaker_threshold": 6,
        "breaker_cooldown": 300.0,
    }
    defaults.update(kw)
    return ReconnectPolicy(**defaults)


def test_exponential_backoff_until_threshold():
    p = _policy()
    # each failure doubles: initial*2**n → 2, 4, 8, 16, 32 (under cap, pre-breaker)
    assert [p.record_failure() for _ in range(5)] == [2.0, 4.0, 8.0, 16.0, 32.0]
    assert not p.breaker_open


def test_backoff_capped_at_max_before_threshold():
    p = _policy(initial_delay=1.0, max_delay=4.0, breaker_threshold=10)
    delays = [p.record_failure() for _ in range(6)]
    # 2, 4, then capped at max_delay=4; breaker not yet tripped
    assert delays == [2.0, 4.0, 4.0, 4.0, 4.0, 4.0]
    assert not p.breaker_open


def test_breaker_opens_at_threshold_and_returns_cooldown():
    p = _policy(breaker_threshold=3, breaker_cooldown=300.0, max_delay=60.0)
    assert p.record_failure() == 2.0  # 1
    assert p.record_failure() == 4.0  # 2
    assert not p.breaker_open
    d = p.record_failure()  # 3rd → threshold
    assert p.breaker_open
    assert d == 300.0  # cooldown, NOT the capped backoff
    assert p.record_failure() == 300.0  # stays open


def test_reset_clears_failures_and_breaker():
    p = _policy(breaker_threshold=2, breaker_cooldown=300.0)
    p.record_failure()
    p.record_failure()
    assert p.breaker_open
    p.reset()
    assert not p.breaker_open
    assert p.consecutive_failures == 0
    assert p.record_failure() == 2.0  # back to initial backoff (initial*2)


def test_invalid_threshold_rejected():
    with pytest.raises(ValueError):
        _policy(breaker_threshold=0)
