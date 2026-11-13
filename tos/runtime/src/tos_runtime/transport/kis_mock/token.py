"""``KisTokenLifecycle`` — the shared KIS OAuth token issuance/expiry/reissue-cooldown state"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.pacer import KisAppKeyPacer, KisPacingRefused

__all__ = [
    "EvidenceRecorder",
    "KisTokenLifecycle",
    "TokenIssuingClient",
    "TokenResponseError",
    "TokenStale",
]


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
        now = self._monotonic.now_ms()
        needs_fresh = self._access_token is None or (
            self._token_issued_at_ms is not None
            and self._token_expires_in_s is not None
            and (now - self._token_issued_at_ms) >= self._token_expires_in_s * 1000
        )
        if not needs_fresh:
            assert self._access_token is not None
            return self._access_token

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
        self._issue_token()
        assert self._access_token is not None
        return self._access_token

    def _issue_token(self) -> None:
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
            raise TokenResponseError(
                "KisTokenLifecycle: token response missing a usable access_token"
            )
        if (
            not isinstance(expires_in, int)
            or isinstance(expires_in, bool)
            or expires_in <= 0
        ):
            raise TokenResponseError(
                "KisTokenLifecycle: token response missing a usable expires_in"
            )
        self._access_token = access_token
        self._token_expires_in_s = expires_in
        self._token_issued_at_ms = self._monotonic.now_ms()
