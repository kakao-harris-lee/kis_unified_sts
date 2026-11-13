"""The KIS credential registry for one boot (C-2 decision (C):"""

from __future__ import annotations

from collections.abc import Callable

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.transport.kis_mock.credential_session import (
    KisCredentialSession,
    KisCredentialSessions,
)
from tos_runtime.transport.kis_mock.pacer import KisPacing
from tos_runtime.transport.kis_mock.token import EvidenceRecorder, TokenIssuingClient
from tos_runtime.transport.kis_quote.config import KisQuoteTransportConfig

__all__ = [
    "KIS_MOCK_APP_KEY_SCOPE",
    "KIS_MOCK_APP_SECRET_SCOPE",
    "KisCredentialSessionsCell",
    "KisCredentialSessionsCellMisuse",
    "build_kis_credential_sessions",
    "kis_mock_credential_session",
    "kis_quote_pacing",
    "kis_transport_pacing",
]


class KisCredentialSessionsCellMisuse(RuntimeError):
    """The cell was driven out of order — a consumer registered after the registry was"""


class KisCredentialSessionsCell:
    """A late-bound slot for this boot's :class:`KisCredentialSessions` (mirrors"""

    def __init__(self) -> None:
        self.sessions: KisCredentialSessions | None = None
        self._on_ready: list[Callable[[KisCredentialSessions], None]] = []

    def on_ready(self, callback: Callable[[KisCredentialSessions], None]) -> None:
        """Register ``callback`` to run at :meth:`start_consumers`."""
        if self.sessions is not None:
            raise KisCredentialSessionsCellMisuse(
                "on_ready() after the cell was filled — a consumer registered too late to be "
                "dispatched, which means it would never acquire its session at all; "
                "registration belongs in the compose root's service-building phase"
            )
        self._on_ready.append(callback)

    def fill(self, sessions: KisCredentialSessions) -> None:
        """Publish the registry WITHOUT dispatching (class docstring's ordering note)."""
        self.sessions = sessions

    def start_consumers(self) -> None:
        """Run every registered callback, after the order transport has taken its session."""
        if self.sessions is None:
            raise KisCredentialSessionsCellMisuse(
                "start_consumers() before fill() — there is no registry to hand out"
            )
        pending, self._on_ready = self._on_ready, []
        for callback in pending:
            callback(self.sessions)


KIS_MOCK_APP_KEY_SCOPE = "kis_mock.app_key"
KIS_MOCK_APP_SECRET_SCOPE = "kis_mock.app_secret"


def kis_transport_pacing(config: KisMockTransportConfig) -> KisPacing:
    """The ``kis_mock.*`` app key's pacing terms from ``kis_mock_transport.yaml`` (issue #970):"""
    return KisPacing(
        min_interval_ms=config.min_send_interval_ms,
        wait_budget_ms=config.app_key_request_wait_budget_ms,
    )


def kis_quote_pacing(config: KisQuoteTransportConfig) -> KisPacing:
    """The same terms from ``kis_quote.yaml`` (the quote intake and the band reader). The"""
    return KisPacing(
        min_interval_ms=config.app_key_min_request_interval_ms,
        wait_budget_ms=config.app_key_request_wait_budget_ms,
    )


def build_kis_credential_sessions(
    *,
    custody: CredentialCustody,
    monotonic: MonotonicSource,
    evidence_sink: EvidenceRecorder,
) -> KisCredentialSessions:
    """This boot's one-session-per-KIS-app-key registry (module docstring)."""
    return KisCredentialSessions(
        custody=custody, monotonic=monotonic, evidence_sink=evidence_sink
    )


def kis_mock_credential_session(
    credential_sessions: KisCredentialSessions,
    *,
    client: TokenIssuingClient,
    token_endpoint_base: str,
    token_path: str,
    token_reissue_min_interval_s: int,
    pacing: KisPacing,
) -> KisCredentialSession:
    """The ``kis_mock.*`` app key's session from ``credential_sessions``."""
    return credential_sessions.session_for(
        client=client,
        app_key_scope=KIS_MOCK_APP_KEY_SCOPE,
        app_secret_scope=KIS_MOCK_APP_SECRET_SCOPE,
        token_endpoint_base=token_endpoint_base,
        token_path=token_path,
        token_reissue_min_interval_s=token_reissue_min_interval_s,
        pacing=pacing,
    )
