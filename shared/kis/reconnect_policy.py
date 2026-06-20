"""Reconnect backoff with a circuit breaker for KIS WebSocket feeds.

KIS explicitly warns that an *unbounded* reconnect loop on a failing connection
can get the customer account blocked server-side ("무한 연결 시도 → 고객 차단").
Plain exponential backoff still pokes a blocked account forever at the cap; this
policy adds a breaker: after ``breaker_threshold`` consecutive failures it backs
off to a long ``breaker_cooldown`` (and stays there) so the feed retries only
slowly — enough to self-heal when KIS recovers, but not enough to sustain a
block. ``reset()`` is called on a successful connect.

Consecutive-failure counting alone, however, cannot catch a *flapping*
connection that succeeds then drops a short while later: each success calls
``reset()`` and zeroes the failure count, so the breaker never opens even though
the feed is churning handshakes all session long (the observed ~105s periodic
drop). To guarantee IP-ban prevention regardless of the drop cause, this policy
also enforces a **reconnect-rate ceiling**: callers record every *successful
reconnect* via :meth:`record_reconnect`, and once more than ``rate_max``
reconnects occur within a rolling ``rate_window`` the breaker trips into the
long cooldown independent of the consecutive-failure count. The rate history
deliberately survives :meth:`reset` — clearing it on each success would defeat
the purpose, since flapping *is* a stream of successes.

Pure/stateful and side-effect-free so it is trivially unit-testable; the feeds
own the actual sleeping and logging.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from time import monotonic


class ReconnectPolicy:
    """Exponential backoff that escalates to a long cooldown once tripped.

    Trips on either condition:
      * ``breaker_threshold`` consecutive failed reconnect attempts, or
      * more than ``rate_max`` reconnects within a rolling ``rate_window`` —
        catches success-then-drop flapping that consecutive counting misses.

    Set ``rate_max <= 0`` to disable the rate ceiling (consecutive-only).
    """

    def __init__(
        self,
        *,
        initial_delay: float,
        max_delay: float,
        breaker_threshold: int,
        breaker_cooldown: float,
        rate_max: int = 0,
        rate_window: float = 0.0,
        time_fn: Callable[[], float] = monotonic,
    ) -> None:
        if breaker_threshold < 1:
            raise ValueError("breaker_threshold must be >= 1")
        self._initial = initial_delay
        self._max = max_delay
        self._breaker_threshold = breaker_threshold
        self._breaker_cooldown = breaker_cooldown
        self._consecutive = 0
        # Reconnect-rate ceiling. _rate_max <= 0 disables it. The deque holds
        # timestamps (time_fn units) of recent reconnects, pruned to _rate_window.
        self._rate_max = rate_max
        self._rate_window = rate_window
        self._time_fn = time_fn
        self._reconnects: deque[float] = deque()
        # Latches once the rate ceiling trips so the breaker stays open through
        # the cooldown even as old reconnect timestamps age out of the window.
        self._rate_tripped = False

    def reset(self) -> None:
        """Clear the failure count after a successful connection.

        Intentionally does NOT clear the reconnect-rate history: a flapping
        connection is a stream of *successes*, so resetting the rate window on
        each one would make the ceiling unreachable. Use
        :meth:`record_reconnect` to feed the rate ceiling.
        """
        self._consecutive = 0

    def record_reconnect(self) -> None:
        """Register a successful (re)connect for the rolling rate ceiling.

        Trips the breaker (latched) once more than ``rate_max`` reconnects fall
        within ``rate_window``. No-op when the rate ceiling is disabled.
        """
        if self._rate_max <= 0 or self._rate_window <= 0:
            return
        now = self._time_fn()
        self._reconnects.append(now)
        cutoff = now - self._rate_window
        while self._reconnects and self._reconnects[0] < cutoff:
            self._reconnects.popleft()
        if len(self._reconnects) > self._rate_max:
            self._rate_tripped = True

    def record_failure(self) -> float:
        """Register a failed attempt; return the delay to wait before retrying.

        Below the threshold: exponential backoff that doubles each failure —
        ``initial * 2**n`` (n = consecutive failures) capped at ``max_delay``, so
        the first failure waits ``2*initial`` (the caller already slept ``initial``
        before the first attempt). At/above the threshold — or once the
        reconnect-rate ceiling has tripped — the breaker cooldown.
        """
        self._consecutive += 1
        if self.breaker_open:
            return self._breaker_cooldown
        return min(self._initial * (2**self._consecutive), self._max)

    @property
    def breaker_open(self) -> bool:
        """True once consecutive failures hit the threshold OR the rate ceiling tripped."""
        return self._rate_tripped or self._consecutive >= self._breaker_threshold

    @property
    def rate_tripped(self) -> bool:
        """True if the reconnect-rate ceiling (flap detector) has tripped."""
        return self._rate_tripped

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive
