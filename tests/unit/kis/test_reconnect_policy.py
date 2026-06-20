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


class _Clock:
    """Manually advanced monotonic clock for deterministic rate-window tests."""

    def __init__(self, start: float = 0.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def test_rate_ceiling_trips_breaker_on_flapping_without_consecutive_failures():
    # Reproduces the production incident: a connection that succeeds then drops
    # on a periodic ~105s cycle. Each cycle calls reset() (zeroing the
    # consecutive-failure count), so consecutive counting NEVER trips the
    # breaker. The rate ceiling must catch it.
    clock = _Clock()
    p = _policy(
        breaker_threshold=6,  # high enough that consecutive counting can't trip
        rate_max=4,
        rate_window=600.0,
        time_fn=clock,
    )
    # Simulate the flap: connect → reset() → drop 105s later → reconnect → ...
    for _ in range(6):
        p.reset()  # success-then-drop never increments consecutive failures
        p.record_reconnect()
        clock.advance(105.0)

    assert p.consecutive_failures == 0  # consecutive counting saw nothing
    assert p.rate_tripped
    assert p.breaker_open  # tripped purely via the rate ceiling
    # Once tripped, record_failure returns the long cooldown, not fast backoff.
    assert p.record_failure() == 300.0


def test_rate_ceiling_disabled_by_default():
    # rate_max defaults to 0 (disabled): unlimited reconnects never trip it.
    p = _policy()
    for _ in range(100):
        p.reset()
        p.record_reconnect()
    assert not p.rate_tripped
    assert not p.breaker_open


def test_rate_window_prunes_old_reconnects():
    # Sparse reconnects spread beyond the window must not accumulate.
    clock = _Clock()
    p = _policy(rate_max=4, rate_window=600.0, time_fn=clock)
    for _ in range(20):
        p.record_reconnect()
        clock.advance(700.0)  # each reconnect is older than the window
    assert not p.rate_tripped


def test_rate_trip_latches_through_reset_and_window_expiry():
    # Once tripped, the breaker stays open even as timestamps age out and reset()
    # is called — so the long cooldown holds for the whole recovery, not just one
    # cycle.
    clock = _Clock()
    p = _policy(rate_max=4, rate_window=600.0, time_fn=clock)
    for _ in range(5):
        p.record_reconnect()
        clock.advance(10.0)
    assert p.rate_tripped
    p.reset()
    clock.advance(10_000.0)  # all timestamps now far outside the window
    assert p.rate_tripped  # latched
    assert p.breaker_open
