import numpy as np
import pytest

from shared.backtest.lookahead_guard import LookaheadGuard, LookaheadGuardMode


@pytest.mark.parametrize("mode,should_raise", [
    (LookaheadGuardMode.OFF, False),
    (LookaheadGuardMode.WARN, False),
    (LookaheadGuardMode.ASSERT, True),
])
def test_lookahead_guard_basic(mode, should_raise, caplog):
    guard = LookaheadGuard(mode=mode)
    arr = np.array([1, 2, 3, 4, 5])
    timestamps = [10, 20, 30, 40, 50]
    context_timestamp = 30
    # arr[3], arr[4] (timestamps 40, 50) are future
    if should_raise:
        with pytest.raises(AssertionError):
            guard.check(arr, timestamps, context_timestamp, "test")
    else:
        guard.check(arr, timestamps, context_timestamp, "test")
        if mode == LookaheadGuardMode.WARN:
            assert any("lookahead" in r.message.lower() for r in caplog.records)


def test_lookahead_guard_no_future():
    guard = LookaheadGuard(mode=LookaheadGuardMode.ASSERT)
    arr = np.array([1, 2, 3])
    timestamps = [10, 20, 30]
    context_timestamp = 30
    # No future values
    guard.check(arr, timestamps, context_timestamp, "test")


def test_lookahead_guard_empty():
    guard = LookaheadGuard(mode=LookaheadGuardMode.ASSERT)
    arr = np.array([])
    timestamps = []
    context_timestamp = 10
    guard.check(arr, timestamps, context_timestamp, "test")


def test_lookahead_guard_warn_logs(caplog):
    guard = LookaheadGuard(mode=LookaheadGuardMode.WARN)
    arr = np.array([1, 2, 3, 4])
    timestamps = [1, 2, 3, 4]
    context_timestamp = 2
    guard.check(arr, timestamps, context_timestamp, "warn-test")
    assert any("lookahead" in r.message.lower() for r in caplog.records)
