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

The rate trip is *self-healing*, not a permanent latch: while it holds, the feed
reconnects only once per cooldown, so the rolling window drains; once the window
falls back to/below ``rate_max`` (the flapping has stopped) the trip clears and
fast reconnect resumes — mirroring how the consecutive breaker recovers on a
clean connect. (A permanent latch would pin a feed at cooldown-spaced reconnects
for the whole process after a single transient flap, long after KIS recovered.)

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

    The rate trip self-heals: it holds only while the rolling window stays above
    ``rate_max``, and clears once the window drains (flapping stopped).

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

        Trips the breaker once more than ``rate_max`` reconnects fall within
        ``rate_window``. No-op when the rate ceiling is disabled.
        """
        if self._rate_enabled:
            self._reconnects.append(self._time_fn())
            self._prune()

    def _prune(self) -> None:
        """Drop reconnect timestamps older than the rolling window."""
        cutoff = self._time_fn() - self._rate_window
        while self._reconnects and self._reconnects[0] < cutoff:
            self._reconnects.popleft()

    @property
    def _rate_enabled(self) -> bool:
        return self._rate_max > 0 and self._rate_window > 0

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
        return self.rate_tripped or self._consecutive >= self._breaker_threshold

    @property
    def rate_tripped(self) -> bool:
        """True while the reconnect-rate ceiling is exceeded (flap detector).

        Evaluated against the live rolling window (old timestamps pruned first),
        so it self-heals: once reconnects within ``rate_window`` fall back to/below
        ``rate_max`` it returns False and fast reconnect resumes.
        """
        if not self._rate_enabled:
            return False
        self._prune()
        return len(self._reconnects) > self._rate_max

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive
