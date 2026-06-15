"""StockPriceFeed reconnect: single-loop guard, lock release, flap self-heal.

Regression for the reconnect-thread explosion: _on_close spawned a reconnect
thread on every WS close, and each reconnect opened a WS whose close spawned
yet another thread. A flapping KIS connection multiplied them exponentially
(~1000 approval requests/sec → 403 rate-limit). The non-blocking _reconnect_lock
collapses concurrent loops to one.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import shared.kis.stock_feed as sf
from shared.kis.auth import KISAuthConfig
from shared.kis.stock_feed import KISStockPriceFeed


def _make_feed() -> KISStockPriceFeed:
    return KISStockPriceFeed(
        config=KISAuthConfig(app_key="k", app_secret="s", is_real=True)
    )


class _FakeThread:
    """Swallows the WS run_forever thread so no real socket is opened."""

    def __init__(self, **kw):
        self._kw = kw

    def start(self):
        pass


@pytest.mark.asyncio
async def test_start_does_not_crash_on_initial_connect_timeout():
    """A failed initial connect must NOT raise — it would crash-loop the daemon.

    Regression: stock_feed.start() set _running=False and raised on connect
    timeout; services/market_ingest does not catch it, so a KIS reset-on-connect
    window restart-looped the container (RestartCount climbing). start() must
    instead keep _running=True (so the WS thread's on_close drives the
    background reconnect) and return without raising.
    """
    feed = _make_feed()
    feed._connection_timeout = 0.0  # _connected.wait() returns False immediately

    with (
        patch.object(feed, "_get_approval_key"),
        patch("shared.kis.stock_feed.websocket.WebSocketApp", return_value=MagicMock()),
        patch("shared.kis.stock_feed.threading.Thread", _FakeThread),
    ):
        await feed.start()  # must NOT raise ConnectionError

    assert feed._running is True  # stays alive for the background reconnect loop


def test_reconnect_noop_when_a_loop_already_holds_the_lock():
    """The guard: while one reconnect loop runs, a concurrent call is a no-op.

    This is what prevents the exponential thread explosion — _on_close can spawn
    as many reconnect threads as it likes; only one ever runs the loop body.
    """
    feed = _make_feed()
    feed._running = True
    approval = MagicMock()
    feed._get_approval_key = approval  # type: ignore[method-assign]

    # Simulate an active reconnect loop already holding the lock.
    assert feed._reconnect_lock.acquire(blocking=False)
    try:
        feed._reconnect()  # must return immediately, never touching approval
    finally:
        feed._reconnect_lock.release()

    approval.assert_not_called()


def test_reconnect_connects_then_releases_lock():
    """A successful reconnect runs one iteration and releases the lock."""
    feed = _make_feed()
    feed._running = True
    feed._connected.clear()
    feed._connection_timeout = 0.0  # wait() returns immediately on current state

    approval = MagicMock(side_effect=lambda: feed._connected.set())

    with (
        patch.object(feed, "_get_approval_key", approval),
        patch("shared.kis.stock_feed.websocket.WebSocketApp", return_value=MagicMock()),
        patch("shared.kis.stock_feed.threading.Thread", _FakeThread),
        patch("shared.kis.stock_feed.time.sleep", lambda *_a, **_k: None),
        patch.object(sf, "_record_ws_metric"),
    ):
        feed._reconnect()

    approval.assert_called_once()
    # Lock released → a subsequent reconnect can acquire it.
    assert feed._reconnect_lock.acquire(blocking=False)
    feed._reconnect_lock.release()


def test_reconnect_persists_until_connected():
    """A failed connect attempt retries instead of returning (flap self-heal).

    Previously the loop returned on a successful wait; with the guard, an
    early return on a flap could leave the feed dead. The loop now keeps
    retrying until the connection is genuinely up.
    """
    feed = _make_feed()
    feed._running = True
    feed._connected.clear()
    feed._connection_timeout = 0.0  # wait() reflects current state, no blocking

    calls = {"n": 0}

    def approve():
        calls["n"] += 1
        if calls["n"] >= 2:
            feed._connected.set()  # only the 2nd attempt establishes the link

    with (
        patch.object(feed, "_get_approval_key", side_effect=approve),
        patch("shared.kis.stock_feed.websocket.WebSocketApp", return_value=MagicMock()),
        patch("shared.kis.stock_feed.threading.Thread", _FakeThread),
        patch("shared.kis.stock_feed.time.sleep", lambda *_a, **_k: None),
        patch.object(sf, "_record_ws_metric"),
    ):
        feed._reconnect()

    assert calls["n"] == 2  # retried after the first attempt failed to connect
    assert feed._reconnect_lock.acquire(blocking=False)  # lock released
    feed._reconnect_lock.release()


def test_reconnect_releases_lock_on_approval_exception():
    """If the loop exits via stop (not running), the lock is still released."""
    feed = _make_feed()
    feed._running = True
    feed._connected.clear()

    def approve():
        # Approval keeps 403-ing; stop the feed so the loop exits deterministically.
        feed._running = False
        raise RuntimeError("403 Forbidden")

    with (
        patch.object(feed, "_get_approval_key", side_effect=approve),
        patch("shared.kis.stock_feed.time.sleep", lambda *_a, **_k: None),
        patch.object(sf, "_record_ws_metric"),
    ):
        feed._reconnect()

    # Even on the error/stop path, finally releases the lock.
    assert feed._reconnect_lock.acquire(blocking=False)
    feed._reconnect_lock.release()


def test_reconnect_breaker_trips_on_open_then_drop_flap():
    """An open-then-immediate-drop flap must escalate the breaker (not reset it).

    KIS can accept the socket (so _on_open sets _connected) then drop it within
    ms. Resetting the breaker on _on_open alone would hold it permanently reset
    and let the flap hammer the approval endpoint — the storm the breaker exists
    to stop. The stability check requires the socket to stay up past
    _reconnect_stability_seconds before the breaker clears; a flap therefore
    counts as a failure, trips the breaker after the threshold, and invalidates
    the cached approval key so the next attempt re-fetches (self-heal).
    """
    feed = _make_feed()
    feed._running = True
    feed._connected.clear()
    feed._connection_timeout = 0.0
    feed._reconnect_breaker_threshold = 3
    feed._reconnect_stability_seconds = 0.01

    invalidated = {"n": 0}

    def fake_sleep(d):
        # The stability sleep is when the flap drops the connection.
        if d == feed._reconnect_stability_seconds:
            feed._connected.clear()

    def inval(*_a, **_k):
        invalidated["n"] += 1
        feed._running = False  # stop the loop once the breaker has self-healed

    with (
        # approval "succeeds" and opens the socket each attempt...
        patch.object(
            feed, "_get_approval_key", side_effect=lambda: feed._connected.set()
        ),
        patch("shared.kis.stock_feed.websocket.WebSocketApp", return_value=MagicMock()),
        patch("shared.kis.stock_feed.threading.Thread", _FakeThread),
        patch("shared.kis.stock_feed.time.sleep", side_effect=fake_sleep),
        patch.object(sf, "_record_ws_metric"),
        patch.object(sf.approval_key_cache, "invalidate", side_effect=inval),
    ):
        feed._reconnect()

    # Breaker opened (≥ threshold flaps) and invalidated the approval key.
    assert invalidated["n"] >= 1
