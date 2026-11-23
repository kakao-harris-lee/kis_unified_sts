"""``SharedTokenCache`` — one KIS app key's OAuth token, shared between tenant processes."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tos_runtime.transport.kis_mock.file_lock import (
    FileLockRefused,
    atomic_private_write,
    exclusive_file_lock,
)

__all__ = [
    "CachedToken",
    "SharedTokenCache",
    "SharedTokenCacheRefused",
    "app_key_fingerprint",
]

_CACHE_VERSION = 1
_FUTURE_TOLERANCE_S = 60
_ENDPOINT_DIGEST_CHARS = 16


class SharedTokenCacheRefused(Exception):
    """The lock on the shared cache was held for the whole wait — nothing was read, written"""


def app_key_fingerprint(app_key: bytes) -> str:
    """The cache key for ``app_key``: its sha256 hex digest, never the key itself."""
    return hashlib.sha256(app_key).hexdigest()


def _system_epoch_s() -> int:
    """The host wall clock in whole seconds (the default :class:`SharedTokenCache` clock)."""
    return int(time.time())


@dataclass(frozen=True)
class CachedToken:
    """One app key's cached token, as the file holds it (wall-clock dated, so another"""

    access_token: str
    issued_at_epoch_s: int
    expires_in_s: int

    def remaining_s(self, now_epoch_s: int) -> int:
        """Seconds of life left at ``now_epoch_s`` (negative once expired)."""
        return self.issued_at_epoch_s + self.expires_in_s - now_epoch_s


class SharedTokenCache:
    """The file-backed, ``flock``-guarded token cache of one or more KIS app keys."""

    def __init__(
        self,
        *,
        path: Path,
        refresh_margin_s: int,
        lock_wait_s: float,
        endpoint_base: str,
        now_epoch_s: Callable[[], int] | None = None,
    ) -> None:
        """Pin the cache file, the early-refresh margin and the lock wait budget."""
        self._path = path
        self._lock_path = path.with_name(path.name + ".lock")
        self._refresh_margin_s = refresh_margin_s
        self._lock_wait_s = lock_wait_s
        self._endpoint_digest = hashlib.sha256(
            endpoint_base.encode("utf-8")
        ).hexdigest()[:_ENDPOINT_DIGEST_CHARS]
        self._now_epoch_s = now_epoch_s or _system_epoch_s

    def entry_key(self, fingerprint: str) -> str:
        """``fingerprint``'s entry name in THIS cache file (issue #1129 LOW 5)."""
        # SAFETY: 같은 앱 키라도 엔드포인트가 다르면 토큰도 다르다 — 캐시 파일을 공유하는 두 테넌트가 base 를 달리 가리키면 모의 토큰이 다른 엔드포인트로 나가 401 을 받고, 그 401 이 주문 POST 면 «불확실 송신» 이 된다
        return f"{fingerprint}.{self._endpoint_digest}"

    @property
    def path(self) -> Path:
        """The cache file this instance reads and writes."""
        return self._path

    @property
    def refresh_margin_s(self) -> int:
        """How long before real expiry an entry is treated as due for reissue."""
        return self._refresh_margin_s

    def now_epoch_s(self) -> int:
        """The wall clock, in whole seconds — the one clock two processes can compare."""
        return self._now_epoch_s()

    @contextmanager
    def exclusive(self) -> Iterator[None]:
        """Hold the cache's exclusive lock for the block, or refuse within the wait budget."""
        try:
            with exclusive_file_lock(self._lock_path, wait_s=self._lock_wait_s):
                yield
        except FileLockRefused as exc:
            raise SharedTokenCacheRefused(f"SharedTokenCache: {exc}") from exc

    def read(self, fingerprint: str) -> tuple[CachedToken | None, str]:
        """This app key's entry and why it is (not) usable. Never raises: an unreadable or"""
        document, reason = self._read_document()
        if document is None:
            return None, reason
        entries = document.get("entries")
        if not isinstance(entries, dict):
            return None, "malformed"
        entry = entries.get(self.entry_key(fingerprint))
        if entry is None:
            return None, "absent"
        token = _parse_entry(entry)
        if token is None:
            return None, "malformed"
        if token.issued_at_epoch_s > self.now_epoch_s() + _FUTURE_TOLERANCE_S:
            return None, "clock_skew"
        return token, "present"

    def write(self, fingerprint: str, *, access_token: str, expires_in_s: int) -> None:
        """Replace this app key's entry, atomically (tmp + rename), mode 0600. The caller"""
        document, _ = self._read_document()
        entries_raw = document.get("entries") if document is not None else None
        entries: dict[str, Any] = (
            dict(entries_raw) if isinstance(entries_raw, dict) else {}
        )
        entries[self.entry_key(fingerprint)] = {
            "access_token": access_token,
            "issued_at_epoch_s": self.now_epoch_s(),
            "expires_in_s": expires_in_s,
        }
        self._write_document({"version": _CACHE_VERSION, "entries": entries})

    def _read_document(self) -> tuple[dict[str, Any] | None, str]:
        """Parse the cache file, or say why it could not be used. A cache that cannot be"""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None, "absent"
        except OSError:
            return None, "unreadable"
        try:
            document = json.loads(raw)
        except ValueError:
            return None, "malformed"
        if not isinstance(document, dict) or document.get("version") != _CACHE_VERSION:
            return None, "malformed"
        return document, "present"

    def _write_document(self, document: dict[str, Any]) -> None:
        """tmp + rename, so a reader never sees a half-written cache."""
        atomic_private_write(self._path, json.dumps(document, separators=(",", ":")))


def _parse_entry(entry: Any) -> CachedToken | None:
    """One entry, or ``None`` when it is not the shape this cache writes."""
    if not isinstance(entry, dict):
        return None
    access_token = entry.get("access_token")
    issued_at = entry.get("issued_at_epoch_s")
    expires_in = entry.get("expires_in_s")
    if not isinstance(access_token, str) or not access_token:
        return None
    for value in (issued_at, expires_in):
        if not isinstance(value, int) or isinstance(value, bool):
            return None
    assert isinstance(issued_at, int) and isinstance(expires_in, int)
    if expires_in <= 0 or issued_at <= 0:
        return None
    return CachedToken(
        access_token=access_token,
        issued_at_epoch_s=issued_at,
        expires_in_s=expires_in,
    )
