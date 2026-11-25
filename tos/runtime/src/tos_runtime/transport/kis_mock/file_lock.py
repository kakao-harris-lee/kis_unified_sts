"""The one exclusive file lock the cross-process KIS app-key state is held under (#1125)."""

from __future__ import annotations

import fcntl
import os
import stat
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
_GROUP_AND_OTHER_BITS = 0o077
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
        _narrow_to_private(directory)
        return
    directory.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
    try:
        os.chmod(directory, _DIR_MODE)
    except OSError:  # pragma: no cover - a directory we cannot chmod is still usable
        pass


def _narrow_to_private(directory: Path) -> None:
    """Tighten an ALREADY existing state directory to 0700 (issue #1129 LOW 4)."""
    # SAFETY: 0755 로 먼저 만들어진 디렉터리를 그냥 쓰면 같은 호스트의 다른 사용자가 토큰 캐시 파일 이름과 크기를 들여다본다
    try:
        mode = stat.S_IMODE(directory.stat().st_mode)
        if mode & _GROUP_AND_OTHER_BITS:
            os.chmod(directory, mode & ~_GROUP_AND_OTHER_BITS)
    except OSError:  # pragma: no cover - a directory we cannot chmod is still usable
        pass


def _sweep_stale_tmp(path: Path, *, keep: Path) -> None:
    """Delete this path's leftover ``*.tmp`` siblings — the caller holds its exclusive lock."""
    # SAFETY: tmp 쓰기와 rename 사이에 죽으면 토큰이 담긴 *.tmp 가 0600 으로 영원히 남는다 (#1129 LOW 3)
    try:
        stale = list(path.parent.glob(f"{path.name}.*.tmp"))
    except OSError:  # pragma: no cover - an unlistable directory sweeps nothing
        return
    for candidate in stale:
        if candidate == keep:
            continue
        try:
            candidate.unlink()
        except OSError:  # pragma: no cover - another owner's file is left alone
            pass


def atomic_private_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via tmp + rename, mode 0600 — a reader never sees half."""
    ensure_private_dir(path.parent)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    _sweep_stale_tmp(path, keep=tmp_path)
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
