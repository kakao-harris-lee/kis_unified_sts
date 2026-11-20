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

    def acquire(self, *, wait_budget_s: float) -> None:
        """Wait for this app key's next cross-process slot, then return so the caller sends."""
        try:
            with exclusive_file_lock(self._lock_path, wait_s=wait_budget_s):
                self._grant_within_budget(wait_budget_s)
        except FileLockRefused as exc:
            raise SharedPacingRefused(f"SharedAppKeyGate: {exc}") from exc

    def _grant_within_budget(self, wait_budget_s: float) -> None:
        """Hold the lock while waiting out the remaining spacing, then record the grant."""
        now = self._now()
        last = self._read_last_grant()
        wait_s = 0.0 if last is None else max(0.0, last + self._min_interval_s - now)
        if wait_s > wait_budget_s:
            raise SharedPacingRefused(
                f"SharedAppKeyGate: this app key's next shared slot is {wait_s:.3f}s away, "
                f"past the {wait_budget_s:.3f}s wait budget — not sent"
            )
        if wait_s > 0:
            self._sleep(wait_s)
        atomic_private_write(self._path, f"{self._now():.6f}\n")

    def _read_last_grant(self) -> float | None:
        """The last grant instant, or ``None`` when the file is absent or not one. An"""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            last = float(raw.strip())
        except ValueError:
            return None
        now = self._now()
        if last > now + self._min_interval_s:
            return None
        return last
