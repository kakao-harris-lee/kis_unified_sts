"""The KIS credential registry for one boot (C-2 decision (C):"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.transport.kis_mock.credential_session import (
    KisCredentialSession,
    KisCredentialSessions,
)
from tos_runtime.transport.kis_mock.pacer import KisPacing
from tos_runtime.transport.kis_mock.shared_pacer import SharedAppKeyGate
from tos_runtime.transport.kis_mock.token import EvidenceRecorder, TokenIssuingClient
from tos_runtime.transport.kis_mock.token_cache import SharedTokenCache
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
    "kis_shared_app_key_gate",
    "kis_shared_token_cache",
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


def kis_shared_token_cache(
    config: KisMockTransportConfig | None,
) -> SharedTokenCache | None:
    """The cross-process token cache ``kis_mock_transport.yaml`` declares, or ``None``."""
    if config is None or config.token_cache_path is None:
        return None
    assert config.token_cache_refresh_margin_s is not None
    return SharedTokenCache(
        path=Path(config.token_cache_path),
        refresh_margin_s=config.token_cache_refresh_margin_s,
        lock_wait_s=(
            config.request_timeout_s + config.app_key_request_wait_budget_ms / 1000.0
        ),
        endpoint_base=config.endpoint_rest_base,
    )


def kis_shared_app_key_gate(
    config: KisMockTransportConfig | None,
) -> SharedAppKeyGate | None:
    """The cross-process request gate ``kis_mock_transport.yaml`` declares, or ``None``."""
    if config is None or config.shared_pacer_path is None:
        return None
    assert config.shared_max_rps is not None
    return SharedAppKeyGate(
        path=Path(config.shared_pacer_path),
        max_rps=config.shared_max_rps,
        window_margin_s=config.shared_window_margin_s,
    )


def build_kis_credential_sessions(
    *,
    custody: CredentialCustody,
    monotonic: MonotonicSource,
    evidence_sink: EvidenceRecorder,
    token_cache: SharedTokenCache | None = None,
    shared_gate: SharedAppKeyGate | None = None,
) -> KisCredentialSessions:
    """This boot's one-session-per-KIS-app-key registry (module docstring)."""
    return KisCredentialSessions(
        custody=custody,
        monotonic=monotonic,
        evidence_sink=evidence_sink,
        token_cache=token_cache,
        shared_gate=shared_gate,
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
