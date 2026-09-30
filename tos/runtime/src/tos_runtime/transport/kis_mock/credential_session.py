"""``KisCredentialSession`` — the single owner of one KIS app key's credentials and token
(C-2 decision, option (C): ``docs/plans/2026-09-23-tos-kis-credential-ownership-decision-c2.md``
§4; implemented under ``docs/plans/2026-09-26-tos-periodic-time-eval-and-witness-wiring-plan.md``
§2 W2).

**Why one owner.** Before this module, the order transport and the quote intake each loaded the
``kis_mock.*`` scopes from custody themselves and each built its own
:class:`~tos_runtime.transport.kis_mock.token.KisTokenLifecycle` for the SAME app key. KIS
allows one token reissue per app key per minute (C-2 §1.2 — a 5 s reissue measured HTTP 403),
so the two lifecycles, unaware of each other, would collide the moment both were configured.
Now one :class:`KisCredentialSession` per app key owns the lifecycle and every custody load of
that key; consumers receive the token and the key/secret handles only inside a ``with`` block
that wraps one request, and the handles are zeroed when the block exits (the same lifetime the
adapters' inline ``with custody.load(...)`` blocks had).

**One per app key — enforced, not hoped for.** :class:`KisCredentialSessions` is the compose
root's registry: it hands every consumer of the same scope pair the SAME session, and refuses a
second consumer whose token endpoint (host, path) or reissue cooldown disagrees with the first
— sharing one token across two different endpoints would be a silent cross-wiring, not a share.

**The witness sees a Protocol, not this class** (C-2 §4, firewall). The reconciliation witness
may import only its ``tos_runtime.recon`` siblings, so it declares its own structural Protocol
(``request_credentials()``) and this class satisfies it; only the compose root connects the two.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos_runtime.custody``/
``tos_runtime.time``/this package's ``token`` module only.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from tos_runtime.custody.ports import CredentialCustody, CredentialHandle
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.token import (
    EvidenceRecorder,
    KisTokenLifecycle,
    TokenIssuingClient,
)

__all__ = [
    "KisAppCredentials",
    "KisCredentialSession",
    "KisCredentialSessionConflict",
    "KisCredentialSessions",
    "KisRequestCredentials",
]


class KisCredentialSessionConflict(Exception):
    """Two consumers of the same app key asked for different token endpoints or cooldowns
    (module docstring — refused rather than silently sharing one token across both)."""


class KisAppCredentials:
    """The app key/secret for ONE request, readable only inside the ``with`` block that
    produced it (the handles are zeroed on exit; a later read raises
    :class:`~tos_runtime.custody.ports.CustodyError`)."""

    def __init__(self, *, key: CredentialHandle, secret: CredentialHandle) -> None:
        self._key = key
        self._secret = secret

    def app_key(self) -> bytes:
        """The app key bytes (a fresh copy)."""
        return self._key.value()

    def app_secret(self) -> bytes:
        """The app secret bytes (a fresh copy)."""
        return self._secret.value()


class KisRequestCredentials:
    """The bearer token plus the :class:`KisAppCredentials` for the same request."""

    def __init__(self, *, access_token: str, app: KisAppCredentials) -> None:
        self.access_token = access_token
        self._app = app

    def app_key(self) -> bytes:
        """The app key bytes (a fresh copy; raises once the block has exited)."""
        return self._app.app_key()

    def app_secret(self) -> bytes:
        """The app secret bytes (a fresh copy; raises once the block has exited)."""
        return self._app.app_secret()


@dataclass(frozen=True)
class _SessionTerms:
    """What two consumers must agree on to share one session."""

    token_endpoint_base: str
    token_path: str
    token_reissue_min_interval_s: int


class KisCredentialSession:
    """The single owner of one KIS app key: its custody scopes and its token lifecycle."""

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
    ) -> None:
        """Wire the session (every argument is forwarded to the one
        :class:`~tos_runtime.transport.kis_mock.token.KisTokenLifecycle` this session owns;
        ``custody``/the two scopes are also the source of :meth:`app_credentials`)."""
        self._custody = custody
        self._app_key_scope = app_key_scope
        self._app_secret_scope = app_secret_scope
        self._lifecycle = KisTokenLifecycle(
            client=client,
            custody=custody,
            app_key_scope=app_key_scope,
            app_secret_scope=app_secret_scope,
            monotonic=monotonic,
            token_path=token_path,
            token_reissue_min_interval_s=token_reissue_min_interval_s,
            evidence_sink=evidence_sink,
        )

    def ensure_token_string(self) -> str:
        """The bearer token for the call about to happen.

        Raises:
            ~tos_runtime.transport.kis_mock.token.TokenStale: Stale and inside the reissue
                cooldown.
        """
        return self._lifecycle.ensure_token_string()

    @contextmanager
    def app_credentials(self) -> Iterator[KisAppCredentials]:
        """The app key/secret, loaded for the duration of the ``with`` block only.

        For a consumer that obtains the token earlier than the key/secret (the order transport
        paces between the two) — :meth:`request_credentials` is the one-step form.
        """
        with (
            self._custody.load(self._app_key_scope) as key_handle,
            self._custody.load(self._app_secret_scope) as secret_handle,
        ):
            yield KisAppCredentials(key=key_handle, secret=secret_handle)

    @contextmanager
    def request_credentials(self) -> Iterator[KisRequestCredentials]:
        """Token + app key/secret for one request, inside the ``with`` block only (C-2 §4).

        The token is obtained first, so a stale token refuses before anything is loaded.

        Raises:
            ~tos_runtime.transport.kis_mock.token.TokenStale: Stale and inside the reissue
                cooldown.
        """
        access_token = self.ensure_token_string()
        with self.app_credentials() as app:
            yield KisRequestCredentials(access_token=access_token, app=app)


class KisCredentialSessions:
    """The compose root's one-session-per-app-key registry (module docstring)."""

    def __init__(
        self,
        *,
        custody: CredentialCustody,
        monotonic: MonotonicSource,
        evidence_sink: EvidenceRecorder,
    ) -> None:
        self._custody = custody
        self._monotonic = monotonic
        self._evidence_sink = evidence_sink
        self._sessions: dict[
            tuple[str, str], tuple[_SessionTerms, KisCredentialSession]
        ] = {}

    def session_for(
        self,
        *,
        client: TokenIssuingClient,
        app_key_scope: str,
        app_secret_scope: str,
        token_endpoint_base: str,
        token_path: str,
        token_reissue_min_interval_s: int,
    ) -> KisCredentialSession:
        """The session for this scope pair — created on first request, shared afterwards.

        ``client`` is used only when this call creates the session; a later consumer's client
        talks to the same endpoint (checked) and is not needed for token issuance.

        Raises:
            KisCredentialSessionConflict: The scope pair already has a session whose token
                endpoint or reissue cooldown differs from this request's.
        """
        key = (app_key_scope, app_secret_scope)
        terms = _SessionTerms(
            token_endpoint_base=token_endpoint_base,
            token_path=token_path,
            token_reissue_min_interval_s=token_reissue_min_interval_s,
        )
        existing = self._sessions.get(key)
        if existing is not None:
            existing_terms, session = existing
            if existing_terms != terms:
                raise KisCredentialSessionConflict(
                    f"KIS app key {app_key_scope!r} is already shared under {existing_terms}, "
                    f"but another consumer asked for {terms} — one app key has one token "
                    "endpoint and one reissue cooldown; align the two transport configs"
                )
            return session
        session = KisCredentialSession(
            client=client,
            custody=self._custody,
            app_key_scope=app_key_scope,
            app_secret_scope=app_secret_scope,
            monotonic=self._monotonic,
            token_path=token_path,
            token_reissue_min_interval_s=token_reissue_min_interval_s,
            evidence_sink=self._evidence_sink,
        )
        self._sessions[key] = (terms, session)
        return session
