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

from collections.abc import Callable

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
    "KisCredentialSessionsCellMisuse",
    "build_kis_credential_sessions",
    "kis_mock_credential_session",
]


class KisCredentialSessionsCellMisuse(RuntimeError):
    """The cell was driven out of order — a consumer registered after the registry was
    published, or consumers were started before it was. Both are compose-root wiring bugs with
    no honest fallback, so they refuse rather than degrade."""


class KisCredentialSessionsCell:
    """A late-bound slot for this boot's :class:`KisCredentialSessions` (mirrors
    ``_session_wiring.SessionInboxCell``'s own idiom).

    The registry is built inside ``_finalize``, but the venue service — and therefore the
    CP-3 band reader it may be handed
    (``docs/plans/2026-10-08-tos-cp3-band-source-wave-plan.md`` §4.2) — is constructed earlier,
    because step 2 needs the loaded Order Construction Policy before the engine exists.

    **:meth:`on_ready` is what keeps a session fault a BOOT refusal** (independent review M1).
    A consumer that merely read the cell lazily would not discover a
    :class:`~tos_runtime.transport.kis_mock.credential_session.KisCredentialSessionConflict`
    — two consumers of one app key disagreeing about the token endpoint or the reissue
    cooldown — until the first decision, hours into a session. Registering a callback instead
    makes the acquisition happen inside :func:`_finalize`, so the conflict surfaces while
    compose is still running, which is what every docstring here already promised.

    **Filling and dispatching are two steps, and the ORDER between them matters**
    (independent review LOW-2). ``KisCredentialSessions.session_for`` creates the shared
    app-key session on its FIRST caller, and that caller's client is the one every later token
    issuance uses — including the order transport's. So the order transport has to be the
    creator, exactly as it was before the band source existed: :meth:`fill` publishes the
    registry, the order transport takes its session, and only then does
    :meth:`start_consumers` let the band reader take the SAME session. Dispatching inside
    :meth:`fill` made the band reader the creator, which would have issued the order
    transport's tokens through a client carrying ``band_source.timeout_ms`` and
    ``kis_quote.yaml``'s plaintext flag.
    """

    def __init__(self) -> None:
        self.sessions: KisCredentialSessions | None = None
        self._on_ready: list[Callable[[KisCredentialSessions], None]] = []

    def on_ready(self, callback: Callable[[KisCredentialSessions], None]) -> None:
        """Register ``callback`` to run at :meth:`start_consumers`.

        Raises:
            KisCredentialSessionsCellMisuse: The cell is already filled. Registration happens
                while the compose root is still building services, strictly before
                ``_finalize`` fills the cell — so a late registration is a WIRING bug, not a
                case to absorb (independent review LOW-1: the "already filled, run it now"
                branch this replaces was unreachable on every path, and deleting it left every
                test green, which is the #838 shape of a clause that decides nothing).
        """
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
        """Run every registered callback, after the order transport has taken its session.

        Raises:
            KisCredentialSessionsCellMisuse: The cell was never filled.
        """
        if self.sessions is None:
            raise KisCredentialSessionsCellMisuse(
                "start_consumers() before fill() — there is no registry to hand out"
            )
        pending, self._on_ready = self._on_ready, []
        for callback in pending:
            callback(self.sessions)


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
