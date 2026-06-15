"""Process-wide cache of KIS WebSocket approval keys, keyed by (app key, env).

The WS approval key (``/oauth2/Approval``) is valid ~24h. Re-issuing it on every
reconnect (and, for futures, on every freshly-built adapter) hammers the KIS auth
endpoint — exactly the churn that can contribute to server-side throttling /
account blocks. This cache lets every feed/adapter reuse a still-valid key
instead of re-fetching. Thread-safe; one instance per process.

The cache key includes ``is_real`` because the real (openapi) and mock (vps)
endpoints issue *different* approval keys for the same app key — mirroring the
REST ``TokenCache`` which keys by app_key + is_real. Callers MUST
``invalidate()`` on an approval/auth failure so a revoked/stale key can be
re-fetched (the WS handshake does not validate the key — only the subsequent
subscription does — so a bad key otherwise lingers until TTL expiry).
"""

from __future__ import annotations

import threading
import time

# Reissue a bit under the 24h validity to avoid using a key right at expiry.
DEFAULT_APPROVAL_TTL_SECONDS = 23 * 3600


class ApprovalKeyCache:
    """Thread-safe ``(app_key, is_real) -> (approval_key, issued_at)`` cache."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict[tuple[str, bool], tuple[str, float]] = {}

    def get(
        self,
        app_key: str,
        is_real: bool,
        ttl: float = DEFAULT_APPROVAL_TTL_SECONDS,
    ) -> str | None:
        """Return a cached approval key for (app_key, is_real) if within *ttl*."""
        with self._lock:
            entry = self._keys.get((app_key, is_real))
            if entry is None:
                return None
            key, issued_at = entry
            if (time.time() - issued_at) >= ttl:
                return None
            return key

    def set(self, app_key: str, is_real: bool, approval_key: str) -> None:
        with self._lock:
            self._keys[(app_key, is_real)] = (approval_key, time.time())

    def invalidate(self, app_key: str, is_real: bool) -> None:
        """Drop the cached key (e.g. after an approval/auth error)."""
        with self._lock:
            self._keys.pop((app_key, is_real), None)


# Shared per-process instance used by all KIS WS feeds/adapters.
approval_key_cache = ApprovalKeyCache()
