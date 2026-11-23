"""``SharedAppKeyGate`` — one request rate for the tenant PROCESSES that share a KIS app key."""

# SAFETY: KIS 모의는 토큰 만료뿐 아니라 EGW00201 호출 한도에도 HTTP 500 을 준다 — 한도는 app key 단위로 프로세스를 가로지른다

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from tos_runtime.transport.kis_mock.file_lock import (
    FileLockRefused,
    atomic_private_write,
    exclusive_file_lock,
)

__all__ = ["SharedAppKeyGate", "SharedPacingRefused"]

_WINDOW_S = 1.0
_WINDOW_MARGIN_S = 0.05


class SharedPacingRefused(Exception):
    """This app key's shared queue could not give a slot inside the wait budget. Nothing was"""


class SharedAppKeyGate:
    """The cross-process request gate of ONE KIS app key (module docstring). Thread-safe by"""

    def __init__(
        self,
        *,
        path: Path,
        max_rps: float,
        now_epoch_s: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        """Pin the grant file and the aggregate rate every holder of this app key shares."""
        if max_rps <= 0:
            raise ValueError("SharedAppKeyGate: max_rps must be positive")
        self._path = path
        self._lock_path = path.with_name(path.name + ".lock")
        self._min_interval_s = 1.0 / max_rps
        self._window_grants = max(1, int(max_rps))
        self._now = now_epoch_s or time.time
        self._sleep = sleep or time.sleep

    @property
    def path(self) -> Path:
        """The file holding this app key's last grant instant."""
        return self._path

    @property
    def min_interval_s(self) -> float:
        """The spacing this gate enforces across every process holding the app key."""
        return self._min_interval_s

    @property
    def window_grants(self) -> int:
        """How many grants this gate allows inside one counted second."""
        return self._window_grants

    def acquire(self, *, wait_budget_s: float) -> None:
        """Wait for this app key's next cross-process slot, then return so the caller sends."""
        try:
            with exclusive_file_lock(self._lock_path, wait_s=wait_budget_s):
                self._grant_within_budget(wait_budget_s)
        except FileLockRefused as exc:
            raise SharedPacingRefused(f"SharedAppKeyGate: {exc}") from exc

    def _grant_within_budget(self, wait_budget_s: float) -> None:
        """Hold the lock while waiting out the remaining spacing, then record the grant."""
        grants = self._read_grants()
        wait_s = self._wait_for_slot(grants, self._now())
        if wait_s > wait_budget_s:
            raise SharedPacingRefused(
                f"SharedAppKeyGate: this app key's next shared slot is {wait_s:.3f}s away, "
                f"past the {wait_budget_s:.3f}s wait budget — not sent"
            )
        if wait_s > 0:
            self._sleep(wait_s)
        kept = (*grants, self._now())[-self._window_grants :]
        atomic_private_write(self._path, "".join(f"{grant:.6f}\n" for grant in kept))

    def _wait_for_slot(self, grants: tuple[float, ...], now: float) -> float:
        """How long until this app key's next slot — the spacing AND the per-second count."""
        if not grants:
            return 0.0
        wait_s = max(0.0, grants[-1] + self._min_interval_s - now)
        if len(grants) >= self._window_grants:
            # SAFETY: 간격만 지키면 1초 창에 max_rps+1 건이 들어간다 (2.0 rps → t · t+0.5 · t+1.0) — 2026-11-23 EGW00201 의 원인이다
            oldest = grants[-self._window_grants]
            wait_s = max(wait_s, oldest + _WINDOW_S + _WINDOW_MARGIN_S - now)
        return wait_s

    def _read_grants(self) -> tuple[float, ...]:
        """This app key's last grant instants, oldest first — ``()`` when unreadable. An"""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return ()
        try:
            grants = tuple(sorted(float(field) for field in raw.split()))
        except ValueError:
            return ()
        now = self._now()
        if any(grant > now + self._min_interval_s for grant in grants):
            return ()
        return grants[-self._window_grants :]
