"""MANDATED test-only seam cross-check: venue <-> time (evidence-consumed, NOT reused) (design #19 §0.4c / §7).

time (ADR-002-008) owns the **calendar-expectation** session phase — ``SessionContext.phase``
(``time/elements.py:191``, ``str | None``, a broker-agnostic calendar identity). venue owns the
**authoritative-current** session phase — its own injected ``observed_session_phase`` token
judged by admitting-set membership. VTG-INV-002 line 153: "Calendar time ... never proves
order-specific tradability", so venue **must not** reuse ``time.SessionContext`` as its
admissibility phase (§0.4c REUSE rejected — the central edge-0 judgement). venue consumes time
evidence as an injected digest/scalar and produces its authoritative phase **separately**.

This file imports the real ``time.SessionContext`` as a **test** to lock the boundary: the two
phase notions are distinct (calendar-expectation vs authoritative-current), and venue does not
embed the time type. A test-only cross-import is **not** a runtime package edge (§3.4(d)/§7.1 —
the import-closure test proves ``tos.time`` is absent from the venue package closure).

Regime tag: predicate / model substrate only; VTG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.time import SessionContext
from tos.venue import VenueConstraintSnapshot

from ._venue_strategies import clean_snapshot


def test_time_owns_calendar_expectation_phase() -> None:
    """(§0.4c) time.SessionContext.phase is the calendar-expectation phase (str | None)."""
    assert "phase" in SessionContext.model_fields
    ctx = SessionContext(phase="continuous_trading")
    assert ctx.phase == "continuous_trading"


def test_venue_produces_authoritative_phase_separately_not_reusing_time() -> None:
    """(§0.4c / VTG-INV-002) venue's observed_session_phase is its own str token, NOT a time.SessionContext."""
    snapshot = clean_snapshot()
    # venue's authoritative phase is a plain injected token — NOT a time.SessionContext field.
    assert snapshot.observed_session_phase == "continuous_trading"
    assert not isinstance(snapshot.observed_session_phase, SessionContext)
    # The venue snapshot does NOT embed a time.SessionContext (edge 0 — calendar ↛ admissibility).
    for name, field in VenueConstraintSnapshot.model_fields.items():
        assert (
            field.annotation is not SessionContext
        ), f"venue snapshot field {name} must not reuse time.SessionContext (§0.4c REUSE rejected)"


def test_calendar_phase_and_authoritative_phase_are_different_domains() -> None:
    """(§0.4c) A calendar phase (time) is an evidence INPUT, never the venue authoritative phase.

    Both are ``str`` tokens, but the venue admissibility decision comes from
    ``session_phase_admits`` over the policy admitting-set — never from a calendar phase directly
    (calendar ↛ tradability, VTG-INV-002 line 153).
    """
    calendar = SessionContext(phase="continuous_trading")
    snapshot = clean_snapshot(observed_session_phase="continuous_trading")
    # Same token value here, but they are carried by distinct types on distinct axes — venue never
    # imports SessionContext to source its authoritative phase.
    assert calendar.phase == snapshot.observed_session_phase
    assert type(calendar) is not type(snapshot)
