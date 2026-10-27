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
and each thread holds at most one slot request at a time, so a caller waits at most about two
intervals. With ``wait_budget_ms`` at two intervals an order is never refused by a background
GET, and a priority queue would only add a starvation rule for the GETs.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.time`` only.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from time import sleep

from tos_runtime.time.sources import MonotonicSource

__all__ = ["KisAppKeyPacer", "KisPacing", "KisPacingRefused"]


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
            return granted_ms
        finally:
            self._lock.release()
