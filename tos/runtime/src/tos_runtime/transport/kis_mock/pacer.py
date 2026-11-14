"""``KisAppKeyPacer`` — one request pacer per KIS app key (issue #970)."""

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
    """Every grant instant :meth:`KisAppKeyPacer.acquire` gave on this thread while the tap was"""

    def __init__(self) -> None:
        self.grants_ms: list[int] = []

    @property
    def first_ms(self) -> int | None:
        """The first grant, or ``None``."""
        return self.grants_ms[0] if self.grants_ms else None


@contextmanager
def first_grant_on_this_thread() -> Iterator[KisGrantTap]:
    """Record the slots granted to THIS thread inside the block (module docstring)."""
    tap = KisGrantTap()
    previous = getattr(_taps, "tap", None)
    _taps.tap = tap
    try:
        yield tap
    finally:
        _taps.tap = previous


class KisPacingRefused(Exception):
    """The next slot on this app key is further away than the wait budget. Nothing was sent"""


@dataclass(frozen=True)
class KisPacing:
    """The two pacing terms of one app key."""

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
        """Wait for this caller's slot, then return so the caller sends at once."""
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
