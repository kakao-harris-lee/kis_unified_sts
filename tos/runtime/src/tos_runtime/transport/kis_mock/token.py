"""``KisTokenLifecycle`` — the shared KIS OAuth token issuance/expiry/reissue-cooldown state"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.pacer import KisAppKeyPacer, KisPacingRefused
from tos_runtime.transport.kis_mock.token_cache import (
    CachedToken,
    SharedTokenCache,
    SharedTokenCacheRefused,
    app_key_fingerprint,
)

__all__ = [
    "EvidenceRecorder",
    "KisTokenLifecycle",
    "TokenIssuingClient",
    "TokenResponseError",
    "TokenStale",
]

# What a failed token POST is allowed to say in an exception message and an evidence row:
# KIS's own fault codes and their human text. Never a credential, never the token (2026-11-20
# — `BROKER_FACTS_OBSERVED` recorded `reason: TokenResponseError` and nothing else, so the
# incident could not be told apart from an endpoint outage without a manual POST).
_RESPONSE_FAULT_FIELDS = ("error_code", "error_description", "msg_cd", "msg1", "rt_cd")
_RESPONSE_FAULT_MAX_CHARS = 200

TOKEN_RESPONSE_ERROR_KIND = "TRANSPORT_TOKEN_RESPONSE_ERROR"
TOKEN_CACHE_KIND = "TRANSPORT_TOKEN_CACHE"


class TokenStale(Exception):
    """The held token has expired and the reissue cooldown has not yet elapsed — this attempt"""


class TokenResponseError(Exception):
    """The token endpoint's response body did not carry a usable ``access_token``/``expires_in``"""


@runtime_checkable
class TokenIssuingClient(Protocol):
    """The one client capability this lifecycle needs — satisfied structurally by"""

    def issue_token(
        self, app_key: bytes, app_secret: bytes, *, path: str
    ) -> dict[str, Any]:
        """POST the token endpoint exactly once; return the raw parsed body."""
        ...


@runtime_checkable
class EvidenceRecorder(Protocol):
    """Records one evidence entry. The compose root adapts this to the real evidence store — this"""

    def __call__(self, kind: str, fields: Mapping[str, Any]) -> None:
        """Durably (from the caller's perspective) record one evidence entry."""
        ...


class KisTokenLifecycle:
    """The KIS OAuth token issuance/expiry/reissue-cooldown state machine (module docstring)."""

    def __init__(
        self,
        *,
        client: TokenIssuingClient,
        custody: CredentialCustody,
        app_key_scope: str,
        app_secret_scope: str,
        monotonic: MonotonicSource,
        token_path: str,
        token_reissue_min_interval_s: int,
        evidence_sink: EvidenceRecorder,
        pacer: KisAppKeyPacer,
        token_cache: SharedTokenCache | None = None,
    ) -> None:
        """Wire this lifecycle's dependencies (all injected — no ambient state)."""
        self._client = client
        self._custody = custody
        self._app_key_scope = app_key_scope
        self._app_secret_scope = app_secret_scope
        self._monotonic = monotonic
        self._token_path = token_path
        self._token_reissue_min_interval_s = token_reissue_min_interval_s
        self._evidence = evidence_sink
        self._pacer = pacer
        self._cache = token_cache

        self._access_token: str | None = None
        self._token_issued_at_ms: int | None = None
        self._token_expires_in_s: int | None = None
        self._last_token_issue_attempt_ms: int | None = None
        self._lock = threading.Lock()

    def ensure_token_string(self) -> str:
        """Return the bearer access token string for the call about to happen. Thread-safe:"""
        budget_ms = self._pacer.pacing.wait_budget_ms
        if not self._lock.acquire(timeout=budget_ms / 1000.0):
            raise KisPacingRefused(
                f"KisTokenLifecycle: another request's token issue held the app key's token for "
                f"the whole {budget_ms} ms wait budget — not sent"
            )
        try:
            return self._ensure_token_string_locked()
        finally:
            self._lock.release()

    def _ensure_token_string_locked(self) -> str:
        if not self._needs_fresh(self._monotonic.now_ms()):
            assert self._access_token is not None
            return self._access_token
        if self._cache is None:
            access_token, expires_in_s = self._issue_with_cooldown()
            self._hold(access_token, expires_in_s)
            return access_token
        return self._ensure_from_shared_cache(self._cache)

    def _needs_fresh(self, now: int) -> bool:
        """Whether the in-memory token is absent or past the lifetime it was held for."""
        return self._access_token is None or (
            self._token_issued_at_ms is not None
            and self._token_expires_in_s is not None
            and (now - self._token_issued_at_ms) >= self._token_expires_in_s * 1000
        )

    def _hold(self, access_token: str, lifetime_s: int) -> None:
        """Hold ``access_token`` in memory for ``lifetime_s`` from now."""
        self._access_token = access_token
        self._token_expires_in_s = max(1, lifetime_s)
        self._token_issued_at_ms = self._monotonic.now_ms()

    def _issue_with_cooldown(self) -> tuple[str, int]:
        """One issuance attempt, behind the reissue cooldown and the app key's pacer. Returns"""
        now = self._monotonic.now_ms()
        if self._last_token_issue_attempt_ms is not None:
            elapsed_since_last_attempt_ms = now - self._last_token_issue_attempt_ms
            cooldown_ms = self._token_reissue_min_interval_s * 1000
            if elapsed_since_last_attempt_ms < cooldown_ms:
                self._evidence(
                    "TRANSPORT_TOKEN_STALE",
                    {
                        "reissue_cooldown_s": self._token_reissue_min_interval_s,
                        "elapsed_ms": elapsed_since_last_attempt_ms,
                        "cooldown_remaining_ms": cooldown_ms
                        - elapsed_since_last_attempt_ms,
                    },
                )
                raise TokenStale(
                    "KisTokenLifecycle: token is stale/absent and the reissue cooldown "
                    f"({self._token_reissue_min_interval_s}s) has not elapsed since the last "
                    "issuance attempt — refusing to reissue within this attempt (decision 4)"
                )

        self._pacer.acquire()
        self._last_token_issue_attempt_ms = now
        return self._issue_token()

    def _ensure_from_shared_cache(self, cache: SharedTokenCache) -> str:
        """The shared-cache path (module docstring of ``token_cache``): every process holding"""
        try:
            with cache.exclusive():
                return self._ensure_under_cache_lock(cache)
        except SharedTokenCacheRefused as exc:
            raise KisPacingRefused(str(exc)) from exc

    def _ensure_under_cache_lock(self, cache: SharedTokenCache) -> str:
        """Read, else issue, else fall back — with this app key's cache entry held exclusively."""
        fingerprint = self._app_key_fingerprint()
        entry, reason = cache.read(fingerprint)
        remaining_s = entry.remaining_s(cache.now_epoch_s()) if entry is not None else 0
        if entry is not None and remaining_s > cache.refresh_margin_s:
            self._adopt(cache, entry, remaining_s, outcome="hit", reason=reason)
            return entry.access_token

        self._evidence(
            TOKEN_CACHE_KIND,
            {"outcome": "miss", "reason": reason, "remaining_s": remaining_s},
        )
        try:
            access_token, expires_in_s = self._issue_with_cooldown()
        except Exception:  # noqa: BLE001 - a cached token outranks a failed refresh
            if entry is None or remaining_s <= 0:
                raise
            # 2026-11-20's failing input: the token is minutes from expiry, the reissue is
            # refused (1/min on this app key, or this process's own cooldown) and a token
            # that still works is right there. Using it is what keeps the session sending.
            self._adopt(cache, entry, remaining_s, outcome="fallback", reason=reason)
            return entry.access_token
        cache.write(fingerprint, access_token=access_token, expires_in_s=expires_in_s)
        self._hold(access_token, expires_in_s - cache.refresh_margin_s)
        self._evidence(
            TOKEN_CACHE_KIND,
            {"outcome": "issued", "reason": reason, "expires_in_s": expires_in_s},
        )
        return access_token

    def _adopt(
        self,
        cache: SharedTokenCache,
        entry: CachedToken,
        remaining_s: int,
        *,
        outcome: str,
        reason: str,
    ) -> None:
        """Take the cached token as this process's own. A hit is held only up to the refresh"""
        lifetime_s = (
            remaining_s - cache.refresh_margin_s if outcome == "hit" else remaining_s
        )
        self._hold(entry.access_token, lifetime_s)
        self._evidence(
            TOKEN_CACHE_KIND,
            {"outcome": outcome, "reason": reason, "remaining_s": remaining_s},
        )

    def _app_key_fingerprint(self) -> str:
        """This app key's cache key — a sha256 digest; the key itself never leaves custody."""
        with self._custody.load(self._app_key_scope) as key_handle:
            return app_key_fingerprint(key_handle.value())

    def _issue_token(self) -> tuple[str, int]:
        """(review F5, preserved verbatim) The app key/secret are loaded inside the narrowest"""
        with (
            self._custody.load(self._app_key_scope) as key_handle,
            self._custody.load(self._app_secret_scope) as secret_handle,
        ):
            body = self._client.issue_token(
                key_handle.value(), secret_handle.value(), path=self._token_path
            )
        access_token = body.get("access_token")
        expires_in = body.get("expires_in")
        if not isinstance(access_token, str) or not access_token:
            raise self._response_error("missing a usable access_token", body)
        if (
            not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or expires_in <= 0
        ):
            raise self._response_error("missing a usable expires_in", body)
        return access_token, expires_in

    def _response_error(self, what: str, body: Mapping[str, Any]) -> TokenResponseError:
        """Record WHY the token POST failed, then build the exception that says it too."""
        fault = _token_response_fault(body)
        self._evidence(TOKEN_RESPONSE_ERROR_KIND, {"what": what, **fault})
        detail = ", ".join(f"{key}={value!r}" for key, value in fault.items())
        return TokenResponseError(
            f"KisTokenLifecycle: token response {what} — {detail}"
        )


def _token_response_fault(body: Mapping[str, Any]) -> dict[str, Any]:
    """KIS's own fault code/message from a token response, and the body's key NAMES."""
    fault: dict[str, Any] = {}
    for field in _RESPONSE_FAULT_FIELDS:
        value = body.get(field)
        if value is None:
            continue
        fault[field] = str(value)[:_RESPONSE_FAULT_MAX_CHARS]
    fault["body_keys"] = sorted(key for key in body if isinstance(key, str))
    return fault
