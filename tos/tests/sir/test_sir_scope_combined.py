"""MANDATED property test — exact scope + combined incidents (SIR-EV-002 / SIR-AC-002; design #28 §5.2).

The second yolk and the cleanest ``EV-L1`` slice (register minimum ``EV-L1/3``, no residual tag).
``scope_exact_combined_no_favorable_subset`` decides whether the combined Active Safety Incident Set is
exact, complete, current and admits **no favorable subset** (ADR-002-027 §10 / §5.5 / §5.6;
SIR-INV-003/004). This file is the design #28 §13 mandated property test for that row, plus the §5.6
line 130 **22-dimension anchor drift** lock.

Both ways (design #28 §7.2): every conjunct satisfied ⇒ ``True``, each conjunct violated individually ⇒
``False``, **and** the §4.4 explicit-empty set stays valid while a malformed ∅ denies (the #26 MAJOR-1
over-sealing lesson).

**Closes no SIR-EV.** SIR-EV-002 is ``EV-L1/3`` — the ``/3`` integration and adversarial evidence is
Phase-1-out. The real common-mode detection is a dependency-graph engine, runtime and +Security (ADR §28
OQ3). Regime tag: exact-scope-combined predicate substrate only; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.sir as s
from hypothesis import given
from hypothesis import strategies as st

from ._sir_strategies import (
    CLEAN_APPLICABLE_DIMENSIONS,
    CLEAN_APPLICABLE_INCIDENTS,
    CLEAN_APPLICABLE_SHARED_CAUSES,
    TRIBOOL,
    clean_active_set,
    clean_dependency_closure,
    clean_member,
    clean_members,
    empty_active_set,
)

#: The ADR §5.6 line 130 dependency-closure dimensions, **independently transcribed** here so a drift
#: between the ADR and :class:`~tos.sir.vocabulary.ClosureDimension` fails loudly (design #28 §7.2 /
#: appendix D). ``過 0 · 不 0`` — exactly twenty-two, ``LEGAL_PORTFOLIO`` included (the v1.1 M4
#: restoration).
_ADR_CLOSURE_DIMENSIONS: frozenset[str] = frozenset(
    {
        "SAFETY_CELL",
        "CAPACITY_DOMAIN",
        "LEGAL_PORTFOLIO",
        "ACCOUNT",
        "BROKER",
        "VENUE",
        "INSTRUMENT",
        "STRATEGY",
        "ORDER",
        "POSITION",
        "COMMITMENT",
        "PROTECTION",
        "CREDENTIAL",
        "ROUTE",
        "SESSION",
        "GENERATION",
        "COMPONENT",
        "ARTIFACT",
        "FAILURE_DOMAIN",
        "EVIDENCE_PATH",
        "EXTERNAL_ACTIVITY",
        "DOWNSTREAM_CONSUMER",
    }
)


def _yolk(
    active_set: s.ActiveSafetyIncidentSet | None,
    closure: s.IncidentDependencyClosure | None = None,
    incidents: frozenset[str] = CLEAN_APPLICABLE_INCIDENTS,
    causes: frozenset[str] = CLEAN_APPLICABLE_SHARED_CAUSES,
    dimensions: frozenset[s.ClosureDimension] = CLEAN_APPLICABLE_DIMENSIONS,
) -> bool:
    """Run the yolk with the clean closure unless one is supplied."""
    return s.scope_exact_combined_no_favorable_subset(
        active_set,
        clean_dependency_closure() if closure is None else closure,
        incidents,
        causes,
        dimensions,
    )


# --- anchor drift: the §5.6 22-dimension catalogue --------------------------


def test_closure_dimension_matches_the_adr_twenty_two_dimension_anchor() -> None:
    """(§7.2 drift) ``ClosureDimension`` equals the ADR §5.6 line 130 22-dimension set."""
    assert {member.value for member in s.ClosureDimension} == _ADR_CLOSURE_DIMENSIONS
    assert len(_ADR_CLOSURE_DIMENSIONS) == 22


def test_mandated_floor_is_every_dimension() -> None:
    """(§5.2 conjunct 4) The mandated floor is the whole catalogue — a caller may require more only."""
    assert frozenset(s.ClosureDimension) == s.MANDATED_CLOSURE_DIMENSION_FLOOR


def test_legal_portfolio_dimension_is_present() -> None:
    """(v1.1 M4) The §5.6 ``legal portfolio`` dimension is restored, not silently dropped."""
    assert s.ClosureDimension.LEGAL_PORTFOLIO in s.MANDATED_CLOSURE_DIMENSION_FLOOR


# --- both ways: the clean combined scope holds ------------------------------


def test_clean_combined_scope_is_exact() -> None:
    """(both-ways positive) Every conjunct satisfied ⇒ the combined scope is exact."""
    assert _yolk(clean_active_set()) is True


def test_absent_set_or_closure_denies() -> None:
    """(∅-seal) An absent set or closure is undecidable ⇒ deny."""
    assert _yolk(None) is False
    assert (
        s.scope_exact_combined_no_favorable_subset(
            clean_active_set(),
            None,
            CLEAN_APPLICABLE_INCIDENTS,
            CLEAN_APPLICABLE_SHARED_CAUSES,
            CLEAN_APPLICABLE_DIMENSIONS,
        )
        is False
    )


# --- ∅ both ways (design #28 §4.4; the #26 MAJOR-1 over-sealing lesson) -----


def test_explicit_empty_active_set_is_valid() -> None:
    """(§4.4 / §5.5:126 / §16:423-424) The no-incident bundle's canonical ∅ representation is valid."""
    assert _yolk(empty_active_set(), incidents=frozenset(), causes=frozenset()) is True


def test_empty_members_with_applicable_incidents_denies() -> None:
    """(§4.4 / §10:311) An empty member tuple with a non-empty applicable set is an omission ⇒ deny."""
    assert _yolk(empty_active_set()) is False


def test_members_with_empty_applicable_set_denies() -> None:
    """(§4.4 both-ways) A surplus member with an empty applicable set is conflicting ⇒ deny."""
    assert _yolk(clean_active_set(), incidents=frozenset(), causes=frozenset()) is False


def test_empty_set_with_a_surplus_shared_dependency_denies() -> None:
    """(§4.4 / §5.5:126) A no-incident canonical set cannot carry a declared shared dependency.

    §5.5 scopes the canonical set to "every suspected or open incident **and shared dependency**
    applicable to an exact Safety Cell and scope". With no applicable incident, a declared shared
    dependency is a surplus — an axis the canonical-union id equality and the applicable-shared-cause
    subset check both leave open, so the ∅ branch carries it.
    """
    surplus = empty_active_set(shared_dependencies=("dep-shared",))
    assert _yolk(surplus, incidents=frozenset(), causes=frozenset()) is False
    # ... while the genuine explicit-empty (no members, no shared dependency) still holds.
    assert _yolk(empty_active_set(), incidents=frozenset(), causes=frozenset()) is True


def test_malformed_empty_set_denies() -> None:
    """(§4.4) An ∅ set that is not positively complete / current cannot be the canonical ∅."""
    unproven = empty_active_set(is_complete=None, is_current=None)
    assert _yolk(unproven, incidents=frozenset(), causes=frozenset()) is False


# --- conjunct 2: canonical union, both ways ---------------------------------


def test_missing_applicable_incident_denies() -> None:
    """(§5.5 / §10:311 forward) A member omitted from the canonical set invalidates it."""
    partial = clean_active_set(
        members=(clean_members()[0],), shared_dependencies=("dep-shared",)
    )
    assert s.active_set_is_canonical_union(partial, CLEAN_APPLICABLE_INCIDENTS) is False
    assert _yolk(partial) is False


def test_surplus_member_denies() -> None:
    """(§5.5 reverse / both-ways) A member that is not applicable is a conflicting set ⇒ deny."""
    surplus = clean_active_set(
        members=(
            *clean_members(),
            clean_member(
                incident_id="inc-surplus",
                lifecycle_state=s.IncidentLifecycleState.CLOSED,
            ),
        )
    )
    assert s.active_set_is_canonical_union(surplus, CLEAN_APPLICABLE_INCIDENTS) is False
    assert _yolk(surplus) is False


def test_member_without_an_id_denies() -> None:
    """(§5.5) A member with no incident identity cannot be part of a canonical union."""
    anonymous = clean_active_set(
        members=(clean_member(incident_id=None), clean_members()[1]),
    )
    assert (
        s.active_set_is_canonical_union(anonymous, CLEAN_APPLICABLE_INCIDENTS) is False
    )


@given(permutation=st.permutations(range(2)))
def test_member_order_does_not_change_the_verdict(permutation: list[int]) -> None:
    """(§4.4 reconcile) The verdict is order-independent — no first-entry judgement."""
    members = clean_members()
    reordered = clean_active_set(members=tuple(members[index] for index in permutation))
    assert _yolk(reordered) is True


# --- conjunct 3: no favorable subset (structural derivation) ----------------


def test_open_parent_denies() -> None:
    """(SIR-INV-004 / §10:310) An open parent invalidates a child-only disposition."""
    parent_open = clean_active_set(
        members=(
            clean_member(
                incident_id="inc-open", lifecycle_state=s.IncidentLifecycleState.CLOSED
            ),
            clean_member(
                incident_id="inc-closed",
                lifecycle_state=s.IncidentLifecycleState.CLOSED,
                parent_id="inc-open",
            ),
        )
    )
    # the parent is CLOSED here, so the derivation is False and the set holds ...
    assert s.no_favorable_subset(parent_open, frozenset()) is True
    # ... but an OPEN parent denies.
    parent_still_open = clean_active_set(
        members=(
            clean_member(
                incident_id="inc-open",
                lifecycle_state=s.IncidentLifecycleState.CONTAINING,
            ),
            clean_member(
                incident_id="inc-closed",
                lifecycle_state=s.IncidentLifecycleState.CLOSED,
                parent_id="inc-open",
            ),
        )
    )
    assert s.no_favorable_subset(parent_still_open, frozenset()) is False


def test_open_child_denies() -> None:
    """(SIR-INV-004 / §10:310) A still-open child leaves the parent's disposition unresolvable."""
    child_open = clean_active_set(
        members=(
            clean_member(
                incident_id="inc-open", lifecycle_state=s.IncidentLifecycleState.CLOSED
            ),
            clean_member(
                incident_id="inc-closed",
                lifecycle_state=s.IncidentLifecycleState.INVESTIGATING,
                parent_id="inc-open",
            ),
        )
    )
    assert s.no_favorable_subset(child_open, frozenset()) is False


def test_dangling_parent_is_conservatively_open() -> None:
    """(model_construct re-catch) A dangling parent hides an open parent ⇒ conservatively deny."""
    forged = s.ActiveSafetyIncidentSet.model_construct(
        members=(
            clean_member(
                incident_id="inc-open",
                lifecycle_state=s.IncidentLifecycleState.CLOSED,
                parent_id="inc-ghost",
            ),
        ),
        shared_dependencies=(),
        is_complete=True,
        is_current=True,
    )
    assert s.no_favorable_subset(forged, frozenset()) is False


@given(resolved_first=TRIBOOL, resolved_second=TRIBOOL)
def test_shared_cause_resolution_is_positively_gated(
    resolved_first: bool | None, resolved_second: bool | None
) -> None:
    """(§5.2 conjunct 3) Two members sharing a cause need **both** positively resolved."""
    shared = clean_active_set(
        members=(
            clean_member(
                incident_id="inc-open",
                lifecycle_state=s.IncidentLifecycleState.CLOSED,
                shared_cause_ids=frozenset({"dep-shared"}),
                resolved=resolved_first,
            ),
            clean_member(
                incident_id="inc-closed",
                lifecycle_state=s.IncidentLifecycleState.CLOSED,
                shared_cause_ids=frozenset({"dep-shared"}),
                resolved=resolved_second,
            ),
        )
    )
    expected = resolved_first is True and resolved_second is True
    assert s.no_favorable_subset(shared, CLEAN_APPLICABLE_SHARED_CAUSES) is expected


def test_two_open_members_with_a_shared_dependency_is_a_common_mode() -> None:
    """(§10:305) Two still-open incidents while a shared dependency is declared ⇒ common mode."""
    both_open = clean_active_set(
        members=(
            clean_member(
                incident_id="inc-open",
                lifecycle_state=s.IncidentLifecycleState.CONTAINING,
            ),
            clean_member(
                incident_id="inc-closed",
                lifecycle_state=s.IncidentLifecycleState.SUSPECTED,
            ),
        )
    )
    assert s.no_favorable_subset(both_open, frozenset()) is False


def test_unrepresented_applicable_shared_cause_denies() -> None:
    """(SIR-INV-004 line 170) An applicable shared cause absent from the set is an omission."""
    assert (
        s.no_favorable_subset(clean_active_set(), frozenset({"dep-unrepresented"}))
        is False
    )


def test_unknown_member_lifecycle_is_conservatively_open() -> None:
    """(§10:314) A member with an unknown lifecycle state counts as open, never as closed."""
    unknown = clean_active_set(
        members=(
            clean_member(incident_id="inc-open", lifecycle_state=None),
            clean_member(
                incident_id="inc-closed",
                lifecycle_state=s.IncidentLifecycleState.SUSPECTED,
            ),
        )
    )
    assert s.no_favorable_subset(unknown, frozenset()) is False


# --- conjunct 4: dependency closure completeness ----------------------------


def test_missing_dimension_denies() -> None:
    """(§5.2 conjunct 4 / §10:303) An unrepresented dimension is an incomplete closure ⇒ deny."""
    present = frozenset(s.ClosureDimension) - {s.ClosureDimension.LEGAL_PORTFOLIO}
    partial = clean_dependency_closure(
        present_dimensions=present,
        affected_ids_by_dimension={
            dimension: frozenset({"x"}) for dimension in present
        },
    )
    assert s.dependency_closure_complete(partial, frozenset()) is False
    assert _yolk(clean_active_set(), closure=partial) is False


def test_missing_affected_id_entry_denies() -> None:
    """(§5.2 conjunct 4 both-ways) A present dimension with no explicit entry is unrepresented."""
    entries = {
        dimension: frozenset({"x"})
        for dimension in s.ClosureDimension
        if dimension is not s.ClosureDimension.ROUTE
    }
    partial = clean_dependency_closure(affected_ids_by_dimension=entries)
    assert s.dependency_closure_complete(partial, frozenset()) is False


def test_explicitly_empty_affected_id_entry_is_represented() -> None:
    """(§5.2 conjunct 4) An **explicitly empty** entry is a represented dimension, not an omission."""
    entries = {dimension: frozenset() for dimension in s.ClosureDimension}
    sparse = clean_dependency_closure(affected_ids_by_dimension=entries)
    assert s.dependency_closure_complete(sparse, frozenset()) is True


@given(unknown=TRIBOOL)
def test_closure_unknown_is_negative_polarity(unknown: bool | None) -> None:
    """(§10:314; §4.3 negative) Only an explicit ``False`` clears; ``None`` contains the broader set."""
    closure = clean_dependency_closure(closure_unknown=unknown)
    assert s.dependency_closure_complete(closure, frozenset()) is (unknown is False)


@given(complete=TRIBOOL)
def test_dependency_closure_complete_flag_is_positive_polarity(
    complete: bool | None,
) -> None:
    """(§4.3 positive) The injected completeness proof admits only on an explicit ``True``."""
    closure = clean_dependency_closure(dependency_closure_complete=complete)
    assert s.dependency_closure_complete(closure, frozenset()) is (complete is True)


def test_completeness_flag_alone_never_admits() -> None:
    """(§14 structure over self-report) A positive flag over an empty closure still denies."""
    hollow = clean_dependency_closure(
        present_dimensions=frozenset(),
        affected_ids_by_dimension={},
        dependency_closure_complete=True,
    )
    assert s.dependency_closure_complete(hollow, frozenset()) is False


# --- conjunct 5-6: complete / current / generation --------------------------


@given(complete=TRIBOOL, current=TRIBOOL)
def test_complete_and_current_are_positive_polarity(
    complete: bool | None, current: bool | None
) -> None:
    """(§10:311; §4.3 positive) Only explicit ``True`` on both admits; ``None`` denies."""
    active_set = clean_active_set(is_complete=complete, is_current=current)
    assert _yolk(active_set) is (complete is True and current is True)


def test_absent_generation_denies() -> None:
    """(§5.4 / §16:427) Without a concrete Incident Generation the fence is unprovable ⇒ deny."""
    forged = s.ActiveSafetyIncidentSet.model_construct(
        members=clean_members(),
        shared_dependencies=("dep-shared",),
        is_complete=True,
        is_current=True,
        incident_generation=None,
        active_set_generation=1,
        safety_cell="cell-1",
    )
    assert _yolk(forged) is False


def test_absent_set_generation_denies() -> None:
    """(§4.4 MAX-floor / §5.4) The group reconcile fails closed when **either** coordinate is unknown.

    Conjunct 6 reconciles the set's two generation coordinates through
    :func:`~tos.sir.state.max_incident_generation`, whose contract is "the newest, or ``None`` the
    moment any member of the group is unknown". A first-entry reading of the group would pass this
    fixture, so the MAX-floor semantic is what the assertion pins.
    """
    forged = s.ActiveSafetyIncidentSet.model_construct(
        members=clean_members(),
        shared_dependencies=("dep-shared",),
        is_complete=True,
        is_current=True,
        incident_generation=5,
        active_set_generation=None,
        safety_cell="cell-1",
    )
    assert _yolk(forged) is False
    assert s.max_incident_generation((5, None)) is None


def test_complete_claim_without_exact_identity_is_unconstructable() -> None:
    """(§2.3 coexistence seal) A complete/current claim with a blank exact identity cannot exist."""
    with pytest.raises((s.ArtifactIntegrityError, ValueError)):
        s.ActiveSafetyIncidentSet(
            active_set_id=None,
            is_complete=True,
            incident_generation=None,
            safety_cell=None,
        )
