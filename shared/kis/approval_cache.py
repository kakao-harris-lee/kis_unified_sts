"""Process-wide cache of KIS WebSocket approval keys, keyed by app key.

The WS approval key (``/oauth2/Approval``) is valid ~24h. Re-issuing it on every
reconnect (and, for futures, on every freshly-built adapter) hammers the KIS auth
endpoint — exactly the churn that can contribute to server-side throttling /
account blocks. This cache lets every feed/adapter reuse a still-valid key for a
given app key instead of re-fetching. Thread-safe; one instance per process.
"""

from __future__ import annotations

import threading
import time

# Reissue a bit under the 24h validity to avoid using a key right at expiry.
DEFAULT_APPROVAL_TTL_SECONDS = 23 * 3600


class ApprovalKeyCache:
    """Thread-safe ``app_key -> (approval_key, issued_at)`` cache."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict[str, tuple[str, float]] = {}

    def get(
        self, app_key: str, ttl: float = DEFAULT_APPROVAL_TTL_SECONDS
    ) -> str | None:
        """Return a cached approval key for *app_key* if still within *ttl*."""
        with self._lock:
            entry = self._keys.get(app_key)
            if entry is None:
                return None
            key, issued_at = entry
            if (time.time() - issued_at) >= ttl:
                return None
            return key

    def set(self, app_key: str, approval_key: str) -> None:
        with self._lock:
            self._keys[app_key] = (approval_key, time.time())

    def invalidate(self, app_key: str) -> None:
        """Drop the cached key (e.g. after an approval/auth error)."""
        with self._lock:
            self._keys.pop(app_key, None)


# Shared per-process instance used by all KIS WS feeds/adapters.
approval_key_cache = ApprovalKeyCache()
