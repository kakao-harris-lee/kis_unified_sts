"""reopen_revives_nothing — unconditional non-revival (design #19 §6.8; VTG-EV-012 substrate).

Regime tag: predicate / model substrate only; VTG-EV-012 NOT_IMPLEMENTED (`/3` + Security
residue); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.venue import OrderAdmissibilityDecision, reopen_revives_nothing


def test_revives_nothing_is_unconditionally_true() -> None:
    """(§22 line 473 / VTG-INV-013 line 197) No revival vector revives a prior decision."""
    assert reopen_revives_nothing() is True


def test_every_revival_vector_still_revives_nothing() -> None:
    """(VTG-INV-013) reopen / halt-release / reconnect / restart / failover / clock / recovery revive nothing."""
    assert (
        reopen_revives_nothing(
            venue_reopened=True,
            halt_released=True,
            reconnected=True,
            restarted=True,
            failed_over=True,
            clock_recovered=True,
            constraint_service_recovered=True,
            prior_decision=object(),
        )
        is True
    )


@given(
    reopened=st.booleans(),
    halt_released=st.booleans(),
    reconnected=st.booleans(),
    restarted=st.booleans(),
    failed_over=st.booleans(),
    clock_recovered=st.booleans(),
    recovered=st.booleans(),
)
def test_property_no_revival_input_changes_the_answer(
    reopened: bool,
    halt_released: bool,
    reconnected: bool,
    restarted: bool,
    failed_over: bool,
    clock_recovered: bool,
    recovered: bool,
) -> None:
    """(property, accept-and-discard) No combination of revival inputs ever yields revival."""
    assert (
        reopen_revives_nothing(
            venue_reopened=reopened,
            halt_released=halt_released,
            reconnected=reconnected,
            restarted=restarted,
            failed_over=failed_over,
            clock_recovered=clock_recovered,
            constraint_service_recovered=recovered,
        )
        is True
    )


def test_model_provides_no_reopen_to_decision_revival_operation() -> None:
    """(§6.8 structural) The decision model has NO reopen -> prior-decision restore path.

    The absence is the seal: there is no method / field that maps a venue reopen back into a
    prior decision or authority — a fresh decision + governed chain is mandatory (§22 line 471).
    """
    forbidden = {
        "revive",
        "restore_decision",
        "reactivate",
        "reinstate_prior_decision",
        "rearm",
        "grant_authority",
    }
    assert forbidden.isdisjoint(dir(OrderAdmissibilityDecision))
