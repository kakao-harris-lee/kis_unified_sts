"""Reconnect backoff with a circuit breaker for KIS WebSocket feeds.

KIS explicitly warns that an *unbounded* reconnect loop on a failing connection
can get the customer account blocked server-side ("무한 연결 시도 → 고객 차단").
Plain exponential backoff still pokes a blocked account forever at the cap; this
policy adds a breaker: after ``breaker_threshold`` consecutive failures it backs
off to a long ``breaker_cooldown`` (and stays there) so the feed retries only
slowly — enough to self-heal when KIS recovers, but not enough to sustain a
block. ``reset()`` is called on a successful connect.

Pure/stateful and side-effect-free so it is trivially unit-testable; the feeds
own the actual sleeping and logging.
"""

from __future__ import annotations


class ReconnectPolicy:
    """Exponential backoff that escalates to a long cooldown once tripped."""

    def __init__(
        self,
        *,
        initial_delay: float,
        max_delay: float,
        breaker_threshold: int,
        breaker_cooldown: float,
    ) -> None:
        if breaker_threshold < 1:
            raise ValueError("breaker_threshold must be >= 1")
        self._initial = initial_delay
        self._max = max_delay
        self._breaker_threshold = breaker_threshold
        self._breaker_cooldown = breaker_cooldown
        self._consecutive = 0

    def reset(self) -> None:
        """Clear the failure count after a successful connection."""
        self._consecutive = 0

    def record_failure(self) -> float:
        """Register a failed attempt; return the delay to wait before retrying.

        Below the threshold: exponential backoff that doubles each failure —
        ``initial * 2**n`` (n = consecutive failures) capped at ``max_delay``, so
        the first failure waits ``2*initial`` (the caller already slept ``initial``
        before the first attempt). At/above the threshold: the breaker cooldown.
        """
        self._consecutive += 1
        if self._consecutive >= self._breaker_threshold:
            return self._breaker_cooldown
        return min(self._initial * (2**self._consecutive), self._max)

    @property
    def breaker_open(self) -> bool:
        """True once consecutive failures have reached the threshold."""
        return self._consecutive >= self._breaker_threshold

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive
