"""The one exclusive file lock the cross-process KIS app-key state is held under (#1125).

Two things about one KIS app key live outside any single tenant process: its OAuth token
(``token_cache``) and its request rate (``shared_pacer``). Both are files, both are shared by
the tenant processes that hold that app key, and both must be read-modify-written by one
process at a time — so both take this lock.

``fcntl.flock`` is per open file description, so two processes (and two fds in one process)
contend as expected, and the kernel releases the lock if a holder dies.
"""

from __future__ import annotations

import fcntl
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

__all__ = [
    "FileLockRefused",
    "PRIVATE_FILE_MODE",
    "atomic_private_write",
    "ensure_private_dir",
    "exclusive_file_lock",
]

PRIVATE_FILE_MODE = 0o600
_DIR_MODE = 0o700
_POLL_S = 0.02


class FileLockRefused(Exception):
    """Another holder kept the lock for the whole wait budget. Nothing was read or written"""


@contextmanager
def exclusive_file_lock(path: Path, *, wait_s: float) -> Iterator[None]:
    """Hold ``path``'s exclusive lock for the block, or refuse within ``wait_s``."""
    ensure_private_dir(path.parent)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, PRIVATE_FILE_MODE)
    try:
        _flock_within_budget(fd, path=path, wait_s=wait_s)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _flock_within_budget(fd: int, *, path: Path, wait_s: float) -> None:
    """Poll for the exclusive lock until the budget runs out. The budget is spent waiting"""
    deadline = time.monotonic() + wait_s
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise FileLockRefused(
                    f"another process held {path} for the whole {wait_s:.1f}s wait "
                    "budget — nothing was issued or sent"
                ) from exc
            time.sleep(_POLL_S)


def ensure_private_dir(directory: Path) -> None:
    """Create ``directory`` 0700 if it is not there (it holds one app key's shared state)."""
    if directory.is_dir():
        return
    directory.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
    try:
        os.chmod(directory, _DIR_MODE)
    except OSError:  # pragma: no cover - a directory we cannot chmod is still usable
        pass


def atomic_private_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via tmp + rename, mode 0600 — a reader never sees half."""
    ensure_private_dir(path.parent)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    fd = os.open(
        tmp_path,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_CLOEXEC,
        PRIVATE_FILE_MODE,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, PRIVATE_FILE_MODE)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
