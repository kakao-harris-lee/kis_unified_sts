"""``KisCredentialSessionsCell`` — the two-step publish/dispatch contract.

Re-review LOW-1/LOW-2 of PR #890. The cell exists because the venue service (and therefore
the CP-3 band reader) is built before ``_finalize`` creates this boot's
:class:`~tos_runtime.transport.kis_mock.credential_session.KisCredentialSessions` registry.
Two rules make that safe, and each is a test here:

* registration must PRECEDE publication — a consumer registering afterwards would never be
  dispatched, so it refuses rather than silently running (LOW-1: the "already filled, run it
  now" branch it replaces was unreachable, and deleting it left every test green);
* publication and dispatch are SEPARATE, so the compose root can let the order transport take
  the shared session first (LOW-2).

Hermetic: no registry is ever really built here — the sessions object is an opaque sentinel,
since none of these rules reads anything off it.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from tos_runtime.compose._kis_credential_wiring import (
    KisCredentialSessionsCell,
    KisCredentialSessionsCellMisuse,
)
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions


def _sentinel() -> KisCredentialSessions:
    """An opaque stand-in — the cell only ever hands it on, never reads it."""
    return cast(KisCredentialSessions, object())


class TestRegistrationPrecedesPublication:
    def test_registering_after_fill_refuses(self) -> None:
        cell = KisCredentialSessionsCell()
        cell.fill(_sentinel())

        with pytest.raises(KisCredentialSessionsCellMisuse) as excinfo:
            cell.on_ready(lambda _sessions: None)

        assert "registered too late" in str(excinfo.value)

    def test_registering_before_fill_is_dispatched_exactly_once(self) -> None:
        """The baseline: without it the refusal above would also pass against a cell that
        never dispatches anything."""
        cell = KisCredentialSessionsCell()
        seen: list[Any] = []
        cell.on_ready(seen.append)
        sessions = _sentinel()

        cell.fill(sessions)
        assert seen == []  # publication alone dispatches nothing (LOW-2)

        cell.start_consumers()
        assert seen == [sessions]

        cell.start_consumers()
        assert seen == [sessions]  # drained, not re-run


class TestDispatchNeedsAPublishedRegistry:
    def test_start_consumers_before_fill_refuses(self) -> None:
        cell = KisCredentialSessionsCell()
        cell.on_ready(lambda _sessions: None)

        with pytest.raises(KisCredentialSessionsCellMisuse) as excinfo:
            cell.start_consumers()

        assert "before fill()" in str(excinfo.value)


class TestACallbackFailureIsTheCallersProblem:
    def test_an_exception_propagates_out_of_start_consumers(self) -> None:
        """This is how a ``KisCredentialSessionConflict`` raised by the band reader becomes a
        BOOT refusal: ``start_consumers`` runs inside ``_finalize``, so whatever a callback
        raises refuses the compose."""
        cell = KisCredentialSessionsCell()

        def _explode(_sessions: KisCredentialSessions) -> None:
            raise RuntimeError("conflict")

        cell.on_ready(_explode)
        cell.fill(_sentinel())

        with pytest.raises(RuntimeError, match="conflict"):
            cell.start_consumers()
