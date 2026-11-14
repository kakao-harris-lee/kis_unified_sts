"""``KisCredentialSession`` — the single owner of one KIS app key's credentials and token"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from tos_runtime.custody.ports import CredentialCustody, CredentialHandle
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.pacer import KisAppKeyPacer, KisPacing
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
    """Two consumers of the same app key asked for different token endpoints, cooldowns or"""


class KisAppCredentials:
    """The app key/secret for ONE request, readable only inside the ``with`` block that"""

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
    pacing: KisPacing


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
        pacing: KisPacing,
    ) -> None:
        """Wire the session (every argument but ``pacing`` is forwarded to the one"""
        self._custody = custody
        self._app_key_scope = app_key_scope
        self._app_secret_scope = app_secret_scope
        self._pacer = KisAppKeyPacer(pacing=pacing, monotonic=monotonic)
        self._lifecycle = KisTokenLifecycle(
            client=client,
            custody=custody,
            app_key_scope=app_key_scope,
            app_secret_scope=app_secret_scope,
            monotonic=monotonic,
            token_path=token_path,
            token_reissue_min_interval_s=token_reissue_min_interval_s,
            evidence_sink=evidence_sink,
            pacer=self._pacer,
        )

    def ensure_token_string(self) -> str:
        """The bearer token for the call about to happen."""
        return self._lifecycle.ensure_token_string()

    @contextmanager
    def app_credentials(self) -> Iterator[KisAppCredentials]:
        """The app key/secret for ONE request, loaded for the duration of the ``with`` block"""
        self._pacer.acquire()
        with (
            self._custody.load(self._app_key_scope) as key_handle,
            self._custody.load(self._app_secret_scope) as secret_handle,
        ):
            yield KisAppCredentials(key=key_handle, secret=secret_handle)

    @contextmanager
    def request_credentials(self) -> Iterator[KisRequestCredentials]:
        """Token + app key/secret for one request, inside the ``with`` block only (C-2 §4)."""
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
        pacing: KisPacing,
    ) -> KisCredentialSession:
        """The session for this scope pair — created on first request, shared afterwards."""
        key = (app_key_scope, app_secret_scope)
        terms = _SessionTerms(
            token_endpoint_base=token_endpoint_base,
            token_path=token_path,
            token_reissue_min_interval_s=token_reissue_min_interval_s,
            pacing=pacing,
        )
        existing = self._sessions.get(key)
        if existing is not None:
            existing_terms, session = existing
            if existing_terms != terms:
                raise KisCredentialSessionConflict(
                    f"KIS app key {app_key_scope!r} is already shared under {existing_terms}, "
                    f"but another consumer asked for {terms} — one app key has one token "
                    "endpoint, one reissue cooldown and one pacer; align the two transport "
                    "configs"
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
            pacing=pacing,
        )
        self._sessions[key] = (terms, session)
        return session
