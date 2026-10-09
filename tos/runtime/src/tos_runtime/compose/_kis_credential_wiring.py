"""The KIS credential registry for one boot (C-2 decision (C):
``docs/plans/2026-09-23-tos-kis-credential-ownership-decision-c2.md`` §4; implemented under
``docs/plans/2026-09-26-tos-periodic-time-eval-and-witness-wiring-plan.md`` §2 W2).

Both KIS consumers — the order transport (:mod:`~tos_runtime.compose._transport_wiring`) and the
``kis_quote`` intake (:mod:`~tos_runtime.compose._marketfeed_wiring`) — take the ``kis_mock.*``
app key's :class:`~tos_runtime.transport.kis_mock.credential_session.KisCredentialSession` from
the SAME :class:`~tos_runtime.transport.kis_mock.credential_session.KisCredentialSessions`, so
one app key has one token lifecycle. This module is neutral ground: the quote wiring keeps its
"no dependency on the order transport wiring" property, and the scope pair is named here once
(C-2 §3 — compose plus the custody allow-list ``custody/file_custody.py``, nothing else).
"""

from __future__ import annotations

from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.credential_session import (
    KisCredentialSession,
    KisCredentialSessions,
)
from tos_runtime.transport.kis_mock.token import EvidenceRecorder, TokenIssuingClient

__all__ = [
    "KIS_MOCK_APP_KEY_SCOPE",
    "KIS_MOCK_APP_SECRET_SCOPE",
    "KisCredentialSessionsCell",
    "build_kis_credential_sessions",
    "kis_mock_credential_session",
]


class KisCredentialSessionsCell:
    """A late-bound slot for this boot's :class:`KisCredentialSessions` (mirrors
    ``_session_wiring.SessionInboxCell``'s own idiom).

    The registry is built inside ``_finalize``, but the venue service — and therefore the
    CP-3 band reader it may be handed
    (``docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md`` §4.2) — is constructed earlier,
    because step 2 needs the loaded Order Construction Policy before the engine exists. A
    consumer that only ever READS the session at call time (the band reader never touches it
    at construction) closes over this cell instead; ``_finalize`` fills it the instant the
    registry exists, which is strictly before the boot replay that can first trigger a read.
    """

    def __init__(self) -> None:
        self.sessions: KisCredentialSessions | None = None

    def read(self) -> KisCredentialSessions | None:
        return self.sessions


#: The two custody scope names of the KIS mock app key (plan 2026-09-10 kis-mock transport §2
#: decision 4) — the ONE compose-side definition: the order transport's provisioning/principal
#: check and both consumers' sessions read these.
KIS_MOCK_APP_KEY_SCOPE = "kis_mock.app_key"
KIS_MOCK_APP_SECRET_SCOPE = "kis_mock.app_secret"


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
) -> KisCredentialSession:
    """The ``kis_mock.*`` app key's session from ``credential_sessions``.

    Raises:
        ~tos_runtime.transport.kis_mock.credential_session.KisCredentialSessionConflict: The
            other consumer already holds this app key under a different token endpoint or
            reissue cooldown.
    """
    return credential_sessions.session_for(
        client=client,
        app_key_scope=KIS_MOCK_APP_KEY_SCOPE,
        app_secret_scope=KIS_MOCK_APP_SECRET_SCOPE,
        token_endpoint_base=token_endpoint_base,
        token_path=token_path,
        token_reissue_min_interval_s=token_reissue_min_interval_s,
    )
