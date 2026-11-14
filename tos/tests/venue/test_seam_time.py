"""MANDATED test-only seam cross-check: venue <-> time (evidence-consumed, NOT reused) (design #19 §0.4c / §7)."""

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
    assert snapshot.observed_session_phase == "continuous_trading"
    assert not isinstance(snapshot.observed_session_phase, SessionContext)
    for name, field in VenueConstraintSnapshot.model_fields.items():
        assert (
            field.annotation is not SessionContext
        ), f"venue snapshot field {name} must not reuse time.SessionContext (§0.4c REUSE rejected)"


def test_calendar_phase_and_authoritative_phase_are_different_domains() -> None:
    """(§0.4c) A calendar phase (time) is an evidence INPUT, never the venue authoritative phase."""
    calendar = SessionContext(phase="continuous_trading")
    snapshot = clean_snapshot(observed_session_phase="continuous_trading")
    assert calendar.phase == snapshot.observed_session_phase
    assert type(calendar) is not type(snapshot)
