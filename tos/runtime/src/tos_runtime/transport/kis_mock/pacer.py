"""``KisAppKeyPacer`` — one request pacer per KIS app key (issue #970).

**Why.** KIS limits calls per second (``EGW00201`` "초당 거래건수를 초과하였습니다"), and the
limit is not per endpoint: a quote GET followed at once by an order POST was throttled on the
mock server (``docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`` ``rate_limits.
_kis.order_endpoint_class_observation_2026_07_30``). Before #950 every KIS call of this
runtime went out from one thread, and only order POSTs were spaced
(``KisMockTransport._enforce_pacing``). Since #950 the fill observer's GETs run on a worker
thread, concurrently with the loop's order POSTs, on the same app key. So the spacing now
lives here, on the app key's one
:class:`~tos_runtime.transport.kis_mock.credential_session.KisCredentialSession` (C-2 decision
(C)), and every request that key makes — order POST, token POST, witness/fill/broker-facts/
quote/band GET — takes a slot from it first.

**What a slot is.** :meth:`KisAppKeyPacer.acquire` returns once ``min_interval_ms`` has passed
on the injected monotonic clock since the previous slot was granted, and records the grant
instant. The caller sends right after it returns, so consecutive requests on one key start at
least ``min_interval_ms`` apart, measured start to start (decision 6 of the kis-mock transport
plan, unchanged: the wait ends before the request's own ``t0``). The lock is held across the
wait, so callers are served one at a time and each one measures from the real previous grant,
not from a reservation that sleep jitter could make early.

**Bounded, fail-closed.** No caller waits longer than ``wait_budget_ms``, the lock wait
included. If it would, :class:`KisPacingRefused` is raised before anything is sent and no slot
is taken; the caller fails closed its own way (the order transport: a ``REJECT`` with
``reason=throttled`` and zero network; the witness: ``WitnessUnavailable``; broker facts and
the band reader: "no observation"). Nothing is retried here.

**No priority.** Order POSTs do not jump ahead of GETs. Two threads use one key (the loop
thread: orders, quotes, band, broker facts; the fill observer's FETCH worker: witness reads),
and each thread holds at most one slot request at a time. A caller's slot is therefore at most
one interval after the other thread's, which is itself at most one interval away: about two
intervals from arrival — plus the other thread's sleep overshoot and whole-ms clock truncation,
a few ms that the ``>`` budget check does not forgive. So with ``wait_budget_ms`` at two
intervals an order is refused because of a background GET only at that boundary (the GET
granted just before the order arrived, with the order then needing the full two intervals plus
jitter); it is rare, not impossible, and it fails closed (unsent ``REJECT``). A priority queue
would remove that edge only by adding a starvation rule for the GETs.

**When did a read start?** :func:`first_grant_on_this_thread` lets a caller learn the grant
instants of the requests its own thread made inside a block. The fill observer's release
snapshot is aged from that instant — the earliest moment the broker state it holds could have
been read — and not from before the pacer wait, which would age a healthy snapshot by a full
interval it spent queued (issue #970; ``posttrade/fill_fetch.SnapshotRead``).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.time`` only.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from time import sleep

from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "KisAppKeyPacer",
    "KisGrantTap",
    "KisPacing",
    "KisPacingRefused",
    "first_grant_on_this_thread",
]

_taps = threading.local()


class KisGrantTap:
    """Every grant instant :meth:`KisAppKeyPacer.acquire` gave on this thread while the tap was
    open, in order. Empty when nothing was granted (nothing was sent)."""

    def __init__(self) -> None:
        self.grants_ms: list[int] = []

    @property
    def first_ms(self) -> int | None:
        """The first grant, or ``None``."""
        return self.grants_ms[0] if self.grants_ms else None


@contextmanager
def first_grant_on_this_thread() -> Iterator[KisGrantTap]:
    """Record the slots granted to THIS thread inside the block (module docstring).
    Other threads' grants are not seen; a nested tap shadows the outer one for its duration.
    """
    tap = KisGrantTap()
    previous = getattr(_taps, "tap", None)
    _taps.tap = tap
    try:
        yield tap
    finally:
        _taps.tap = previous


class KisPacingRefused(Exception):
    """The next slot on this app key is further away than the wait budget. Nothing was sent
    and no slot was taken (module docstring)."""


@dataclass(frozen=True)
class KisPacing:
    """The two pacing terms of one app key.

    Attributes:
        min_interval_ms: Least spacing between two consecutive requests on the key, start to
            start.
        wait_budget_ms: Longest a caller may wait for its slot, lock wait included.
    """

    min_interval_ms: int
    wait_budget_ms: int

    def __post_init__(self) -> None:
        if self.min_interval_ms <= 0 or self.wait_budget_ms <= 0:
            raise ValueError(
                "KisPacing: min_interval_ms and wait_budget_ms must both be positive"
            )


class KisAppKeyPacer:
    """Grants request slots on one app key (module docstring). Thread-safe."""

    def __init__(self, *, pacing: KisPacing, monotonic: MonotonicSource) -> None:
        self._pacing = pacing
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._last_grant_ms: int | None = None

    @property
    def pacing(self) -> KisPacing:
        """The terms this pacer enforces."""
        return self._pacing

    def acquire(self) -> int:
        """Wait for this caller's slot, then return so the caller sends at once.

        Returns:
            The grant instant on the injected monotonic clock.

        Raises:
            KisPacingRefused: The slot would come later than ``wait_budget_ms`` from now.
        """
        budget_ms = self._pacing.wait_budget_ms
        arrived_ms = self._monotonic.now_ms()
        if not self._lock.acquire(timeout=budget_ms / 1000.0):
            raise KisPacingRefused(
                f"KIS app-key pacer: another request held the key for the whole "
                f"{budget_ms} ms wait budget — not sent"
            )
        try:
            now_ms = self._monotonic.now_ms()
            wait_ms = 0
            if self._last_grant_ms is not None:
                wait_ms = max(
                    0, self._last_grant_ms + self._pacing.min_interval_ms - now_ms
                )
            waited_ms = now_ms - arrived_ms
            if waited_ms + wait_ms > budget_ms:
                raise KisPacingRefused(
                    f"KIS app-key pacer: next slot in {wait_ms} ms after {waited_ms} ms "
                    f"queued exceeds the {budget_ms} ms wait budget — not sent"
                )
            if wait_ms > 0:
                sleep(wait_ms / 1000.0)
            granted_ms = self._monotonic.now_ms()
            self._last_grant_ms = granted_ms
            tap = getattr(_taps, "tap", None)
            if tap is not None:
                tap.grants_ms.append(granted_ms)
            return granted_ms
        finally:
            self._lock.release()
