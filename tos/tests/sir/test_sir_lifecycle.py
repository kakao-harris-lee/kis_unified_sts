"""Incident lifecycle anchor drift + CLOSED-is-not-live regression (design #28 §2.2/§7.2; ADR §9).

The ADR §9 line 278-286 lifecycle is a **manually transcribed** anchor, so this file re-transcribes it
independently and asserts the enum still matches. It also locks the three §9 rules that a lifecycle
state could otherwise be misread into a permission: ``SUSPECTED`` is restrictive (line 290), ``CLOSED``
is administrative only and transitions to no live state (line 295), and nothing automatically advances
the lifecycle (line 297).

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.sir as s

from ._sir_strategies import clean_active_set, clean_member, empty_active_set

#: The ADR §9 line 278-286 lifecycle, **independently transcribed** in ADR order (design #28 §7.2 /
#: appendix D). ``過 0 · 不 0`` — exactly eight states.
_ADR_LIFECYCLE: tuple[str, ...] = (
    "SUSPECTED",
    "DECLARED",
    "CONTAINING",
    "STABILIZED_NON_LIVE",
    "INVESTIGATING",
    "REMEDIATION_PENDING",
    "ELIGIBLE_FOR_CLOSURE",
    "CLOSED",
)

#: The ADR §5.3 / §9 line 296 record version states, independently transcribed. ``過 0 · 不 0`` — four.
_ADR_RECORD_STATES: frozenset[str] = frozenset(
    {"DRAFT", "ACTIVE", "SUPERSEDED", "REOPENED"}
)

#: The ADR §5.10 line 146 closure results, independently transcribed. ``過 0 · 不 0`` — three.
_ADR_CLOSURE_RESULTS: tuple[str, ...] = ("DENY", "HOLD", "CLOSE_ADMINISTRATIVELY")


def test_lifecycle_matches_the_adr_eight_state_anchor() -> None:
    """(§7.2 drift) ``IncidentLifecycleState`` equals the ADR §9 line 278-286 8-state flow, in order."""
    assert tuple(member.value for member in s.IncidentLifecycleState) == _ADR_LIFECYCLE
    assert tuple(state.value for state in s.INCIDENT_LIFECYCLE_ORDER) == _ADR_LIFECYCLE
    assert len(_ADR_LIFECYCLE) == 8


def test_record_state_matches_the_adr_four_member_anchor() -> None:
    """(§7.2 drift) ``IncidentRecordState`` equals the ADR §5.3 / §9:296 4-member version set."""
    assert {member.value for member in s.IncidentRecordState} == _ADR_RECORD_STATES
    assert len(_ADR_RECORD_STATES) == 4


def test_closure_result_matches_the_adr_three_token_anchor() -> None:
    """(§7.2 drift) ``ClosureDecisionResult`` equals the ADR §5.10 line 146 3-token result set."""
    assert (
        tuple(member.value for member in s.ClosureDecisionResult)
        == _ADR_CLOSURE_RESULTS
    )
    assert len(_ADR_CLOSURE_RESULTS) == 3


def test_every_non_closed_state_is_restrictive() -> None:
    """(§9 line 290/295) Every pre-closure state is restrictive; ``CLOSED`` alone is not."""
    assert (
        frozenset(s.IncidentLifecycleState) - {s.IncidentLifecycleState.CLOSED}
        == s.RESTRICTIVE_LIFECYCLE_STATES
    )
    assert len(s.RESTRICTIVE_LIFECYCLE_STATES) == 7
    assert s.IncidentLifecycleState.SUSPECTED in s.RESTRICTIVE_LIFECYCLE_STATES
    assert (
        s.IncidentLifecycleState.ELIGIBLE_FOR_CLOSURE in s.RESTRICTIVE_LIFECYCLE_STATES
    )
    assert s.IncidentLifecycleState.CLOSED not in s.RESTRICTIVE_LIFECYCLE_STATES


def test_closed_grants_no_authority() -> None:
    """(§9 line 295; SIR-INV-001) ``CLOSED`` transitions to no live state and grants nothing.

    "``CLOSED`` is administrative only and does not transition to ``ACTIVE``, ``ARMED``, ``READY``, or
    any live state." No lifecycle member appears anywhere in the all-false authority block, and no
    predicate reads a lifecycle state as permission — the all-false authority is carried by the artifact
    regardless of its state.
    """
    all_closed = clean_active_set(
        members=(
            clean_member(
                incident_id="inc-open", lifecycle_state=s.IncidentLifecycleState.CLOSED
            ),
            clean_member(
                incident_id="inc-closed",
                lifecycle_state=s.IncidentLifecycleState.CLOSED,
            ),
        ),
        state=s.IncidentLifecycleState.CLOSED,
    )
    # a fully-closed set carries no dominating open incident ...
    assert s.dominating_open_incident_present(all_closed) is False
    # ... but still grants nothing.
    assert s.all_false_incident_authority(all_closed.authority_effect) is True


def test_no_lifecycle_state_advances_itself() -> None:
    """(§9 line 297) No advance / transition surface exists — nothing auto-advances the lifecycle.

    "No timer, task count, message acknowledgement, absence of alerts, or human status automatically
    advances the lifecycle." The package therefore authors no transition function at all.
    """
    for forbidden in (
        "advance_lifecycle",
        "transition_lifecycle",
        "next_lifecycle_state",
        "lifecycle_transition",
        "LIFECYCLE_TRANSITIONS",
    ):
        assert not hasattr(s, forbidden), (
            f"{forbidden} would automate a lifecycle advance — ADR-002-027 §9 line 297 forbids any "
            "automatic advance and design #28 §0.2 keeps the state machine runtime-owned"
        )


def test_dominating_presence_is_conservative_on_an_unproven_set() -> None:
    """(§3.6/§4.4) An absent or unproven set yields a dominating presence, never a silent clear."""
    assert s.dominating_open_incident_present(None) is True
    assert (
        s.dominating_open_incident_present(clean_active_set(is_complete=None)) is True
    )
    assert s.dominating_open_incident_present(clean_active_set(is_current=None)) is True


def _all_closed_members() -> tuple[s.ActiveSetMember, ...]:
    """Two members, **both** ``CLOSED`` — so the member branch cannot mask the proof branch."""
    return (
        clean_member(
            incident_id="inc-open", lifecycle_state=s.IncidentLifecycleState.CLOSED
        ),
        clean_member(
            incident_id="inc-closed", lifecycle_state=s.IncidentLifecycleState.CLOSED
        ),
    )


def test_unproven_completeness_dominates_with_no_open_member() -> None:
    """(§10 line 311; branch isolation) The proof branch alone yields a dominating presence.

    Every other fixture in this suite carries at least one still-open member, so the member branch
    (``any(_member_is_open(...))``) would return ``True`` on its own and **mask** a deleted
    completeness / currency branch. These fixtures have **no** open member at all, so only the
    positive-polarity proof branch can produce the conservative ``True`` — deleting it flips them.
    """
    for unproven in (None, False):
        no_completeness = clean_active_set(
            members=_all_closed_members(), is_complete=unproven
        )
        assert s.dominating_open_incident_present(no_completeness) is True
        no_currency = clean_active_set(
            members=_all_closed_members(), is_current=unproven
        )
        assert s.dominating_open_incident_present(no_currency) is True
    # ... while the same member tuple with both proofs positive clears (both ways).
    proven = clean_active_set(members=_all_closed_members())
    assert s.dominating_open_incident_present(proven) is False


def test_unproven_empty_set_dominates() -> None:
    """(§4.4 / branch isolation) An ∅ set without positive proofs is not the canonical no-incident ∅.

    ``members = ()`` makes the member branch vacuously ``False``, so this isolates the proof branch on
    the explicit-empty path as well: only a **positively** complete and current ∅ clears.
    """
    assert s.dominating_open_incident_present(empty_active_set(is_current=None)) is True
    assert (
        s.dominating_open_incident_present(empty_active_set(is_complete=None)) is True
    )
    assert s.dominating_open_incident_present(empty_active_set()) is False


def test_valid_explicit_empty_set_has_no_dominating_incident() -> None:
    """(§4.4) The canonical no-incident ∅ set positively clears — over-sealing it would be a defect."""
    assert s.dominating_open_incident_present(empty_active_set()) is False
