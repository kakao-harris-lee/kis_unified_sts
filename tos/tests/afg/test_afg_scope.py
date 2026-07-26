"""core §5.1 — scope-graph completeness, C1 shared-limit direction, envelope not enlarged.

AFG-EV-001 substrate (ADR-002-022 §10; AFG-INV-001; §1 line 25). Every guard carries a
**both-ways** canary: the forbidden direction (the guard fires) *and* the permitted
direction (a legitimate admission is not blocked) — a vacuous grant is a safety defect and
a vacuous block is an availability defect (design #16 §4.7).

The centrepiece is the **C1 two-rule** property: v1.0 of the design transcribed §10 line
276 as "smallest", which was a fail-open direction inversion. The two rules point in
opposite directions and are tested separately:

* unknown dependency / unproven independence => **smallest** conservative containing scope
  (§1 line 25);
* broker documentation not verified-complete => **largest** credible containing scope
  (§10 line 276).

Closes **no** AFG-EV: predicate / coordinate substrate only (design #16 §1).
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.afg import (
    ActionFlowResult,
    ActionFlowScopeKind,
    DocumentedScopeStatus,
    ScopeIndependenceEvidence,
    broadest_scope,
    envelope_not_enlarged,
    narrowest_scope,
    scope_graph_complete,
    shared_limit_conservative,
)
from tos.rcl import CapacityComponent, CapacityVector

from ._afg_strategies import (
    BROKER_REQUEST_DIM,
    REQUIRED_SCOPES,
    SCOPE_SETS,
    independent_evidence,
    issue_snapshot,
    limit_vector,
)

_CREDIBLE_CONTAINING = frozenset(
    {
        ActionFlowScopeKind.GLOBAL,
        ActionFlowScopeKind.BROKER,
        ActionFlowScopeKind.ACCOUNT,
    }
)


# ---------------------------------------------------------------------------
# scope_graph_complete (§10 line 274-278; AFG-INV-001)
# ---------------------------------------------------------------------------


def test_complete_scope_graph_with_independence_passes() -> None:
    """(canary + §5.1) Every required scope covered + independence evidenced => True."""
    assert (
        scope_graph_complete(
            issue_snapshot(),
            REQUIRED_SCOPES,
            producer_self_declared_scope=False,
        )
        is True
    )


def test_missing_scope_fails_closed() -> None:
    """(canary - §10:276) One omitted credential / route scope => False (guard fires)."""
    for omitted in (ActionFlowScopeKind.CREDENTIAL, ActionFlowScopeKind.ROUTE):
        remaining = tuple(sorted(REQUIRED_SCOPES - {omitted}))
        snapshot = issue_snapshot(
            covered_scopes=remaining,
            scope_independence=tuple(
                independent_evidence(scope) for scope in remaining
            ),
        )
        assert (
            scope_graph_complete(
                snapshot, REQUIRED_SCOPES, producer_self_declared_scope=False
            )
            is False
        )


def test_none_snapshot_fails_closed() -> None:
    """(fail-closed) A ``None`` snapshot proves nothing => False."""
    assert (
        scope_graph_complete(None, REQUIRED_SCOPES, producer_self_declared_scope=False)
        is False
    )


def test_empty_required_scope_set_is_not_vacuous_completeness() -> None:
    """(∅ §4.7 row 1) An empty required-scope set is restrictive, never "complete over nothing"."""
    assert (
        scope_graph_complete(
            issue_snapshot(), frozenset(), producer_self_declared_scope=False
        )
        is False
    )


def test_local_counter_only_basis_creates_no_headroom() -> None:
    """(canary - §10:278) A local-counter-only independence basis => False (no headroom)."""
    scopes = tuple(sorted(REQUIRED_SCOPES))
    snapshot = issue_snapshot(
        scope_independence=tuple(
            independent_evidence(
                scope,
                basis_is_local_counter_only=(scope is ActionFlowScopeKind.SESSION),
            )
            for scope in scopes
        )
    )
    assert (
        scope_graph_complete(
            snapshot, REQUIRED_SCOPES, producer_self_declared_scope=False
        )
        is False
    )


def test_scheduler_priority_only_basis_creates_no_headroom() -> None:
    """(canary - §10:278) A scheduler-priority-only basis => False (priority is not capacity)."""
    scopes = tuple(sorted(REQUIRED_SCOPES))
    snapshot = issue_snapshot(
        scope_independence=tuple(
            independent_evidence(
                scope,
                basis_is_scheduler_priority_only=(scope is ActionFlowScopeKind.ROUTE),
            )
            for scope in scopes
        )
    )
    assert (
        scope_graph_complete(
            snapshot, REQUIRED_SCOPES, producer_self_declared_scope=False
        )
        is False
    )


def test_unknown_independence_basis_fails_closed() -> None:
    """(fail-closed) A ``None`` independence axis is UNKNOWN, never "separated by default"."""
    scopes = tuple(sorted(REQUIRED_SCOPES))
    snapshot = issue_snapshot(
        scope_independence=tuple(
            independent_evidence(scope, refill_separated=None) for scope in scopes
        )
    )
    assert (
        scope_graph_complete(
            snapshot, REQUIRED_SCOPES, producer_self_declared_scope=False
        )
        is False
    )


def test_every_adr_separation_axis_is_load_bearing() -> None:
    """(§10:278 six axes) Dropping **any** one of the six separation axes fails closed.

    ADR §10 line 278 verbatim names six axes — "allocation, refill, broker enforcement,
    **credential/session state**, failure domain, and final route". A partial-evidence
    claim on any one of them is not independence, so each axis is exercised individually
    (the credential/session axis was the one the design contract's prose omitted; see the
    design-#16 v1.2 errata).
    """
    scopes = tuple(sorted(REQUIRED_SCOPES))
    axes = ScopeIndependenceEvidence._SEPARATION_AXES
    assert len(axes) == 6, "ADR §10 line 278 declares exactly six separation axes"
    assert "credential_session_state_separated" in axes
    for axis in axes:
        for value in (False, None):
            snapshot = issue_snapshot(
                scope_independence=tuple(
                    independent_evidence(scope, **{axis: value}) for scope in scopes
                )
            )
            assert (
                scope_graph_complete(
                    snapshot, REQUIRED_SCOPES, producer_self_declared_scope=False
                )
                is False
            ), f"{axis}={value!r} must fail the independence check"


def test_credential_session_state_axis_is_required_for_independence() -> None:
    """(§10:278 axis 4, regression) A credential/session-unseparated scope is not independent."""
    evidence = independent_evidence(
        ActionFlowScopeKind.SESSION, credential_session_state_separated=None
    )
    assert evidence.is_independent() is False
    # Causal isolation: only that axis changes and the verdict flips.
    assert independent_evidence(ActionFlowScopeKind.SESSION).is_independent() is True


def test_absent_independence_record_fails_closed() -> None:
    """(fail-closed) A covered scope with **no** independence record => False."""
    snapshot = issue_snapshot(scope_independence=())
    assert (
        scope_graph_complete(
            snapshot, REQUIRED_SCOPES, producer_self_declared_scope=False
        )
        is False
    )


def test_producer_self_declared_scope_is_rejected() -> None:
    """(canary 'delegate-to-producer' §8:248) A producer-declared scope => False; unknown too."""
    snapshot = issue_snapshot()
    assert (
        scope_graph_complete(
            snapshot, REQUIRED_SCOPES, producer_self_declared_scope=True
        )
        is False
    )
    assert (
        scope_graph_complete(
            snapshot, REQUIRED_SCOPES, producer_self_declared_scope=None
        )
        is False
    )


@given(required=SCOPE_SETS)
def test_scope_completeness_never_passes_without_full_coverage(
    required: frozenset[ActionFlowScopeKind],
) -> None:
    """(property) ``True`` only when the required set is non-empty and fully covered+evidenced."""
    snapshot = issue_snapshot()
    verdict = scope_graph_complete(
        snapshot, required, producer_self_declared_scope=False
    )
    covered = frozenset(snapshot.covered_scopes)
    expected = bool(required) and required <= covered
    assert verdict is expected


# ---------------------------------------------------------------------------
# shared_limit_conservative (C1 — the two opposite conservative rules)
# ---------------------------------------------------------------------------


def test_c1_rule2_incomplete_broker_documentation_widens_to_largest() -> None:
    """(C1 rule 2, §10:276 canary -) Incomplete documentation => LARGEST credible scope."""
    for status in (
        DocumentedScopeStatus.INCOMPLETE,
        DocumentedScopeStatus.CONTRADICTORY,
        DocumentedScopeStatus.STALE,
        DocumentedScopeStatus.UNVERIFIED,
        None,
    ):
        verdict = shared_limit_conservative(
            status,
            ActionFlowScopeKind.ACCOUNT,
            _CREDIBLE_CONTAINING,
            True,
        )
        assert verdict is ActionFlowScopeKind.GLOBAL, (
            "an incompletely documented broker scope must be treated as shared across "
            "the LARGEST credible containing scope (§10 line 276), not the smallest"
        )


def test_c1_rule1_unproven_independence_expands_to_smallest() -> None:
    """(C1 rule 1, §1:25 canary -) Unproven independence => SMALLEST containing scope."""
    for evidence in (False, None):
        verdict = shared_limit_conservative(
            DocumentedScopeStatus.VERIFIED_COMPLETE,
            ActionFlowScopeKind.ACCOUNT,
            _CREDIBLE_CONTAINING,
            evidence,
        )
        assert verdict is ActionFlowScopeKind.ACCOUNT
    # The rule genuinely selects the narrowest member, not merely the claimed scope.
    verdict = shared_limit_conservative(
        DocumentedScopeStatus.VERIFIED_COMPLETE,
        ActionFlowScopeKind.GLOBAL,
        _CREDIBLE_CONTAINING,
        None,
    )
    assert verdict is ActionFlowScopeKind.ACCOUNT


def test_c1_two_rules_point_in_opposite_directions() -> None:
    """(C1 direction seal) The two rules resolve the SAME credible set to opposite ends."""
    widened = shared_limit_conservative(
        DocumentedScopeStatus.INCOMPLETE,
        ActionFlowScopeKind.ACCOUNT,
        _CREDIBLE_CONTAINING,
        True,
    )
    narrowed = shared_limit_conservative(
        DocumentedScopeStatus.VERIFIED_COMPLETE,
        ActionFlowScopeKind.ACCOUNT,
        _CREDIBLE_CONTAINING,
        None,
    )
    assert widened is broadest_scope(_CREDIBLE_CONTAINING)
    assert narrowed is narrowest_scope(_CREDIBLE_CONTAINING)
    assert widened is not narrowed


def test_c1_positive_side_keeps_the_claimed_scope() -> None:
    """(canary + §5.1) Verified-complete documentation + evidenced independence keeps the claim."""
    verdict = shared_limit_conservative(
        DocumentedScopeStatus.VERIFIED_COMPLETE,
        ActionFlowScopeKind.ACCOUNT,
        _CREDIBLE_CONTAINING,
        True,
    )
    assert verdict is ActionFlowScopeKind.ACCOUNT


def test_empty_credible_containing_scopes_is_unknown() -> None:
    """(∅ §4.7 row 9) An empty credible-containing set => UNKNOWN (no scope establishable)."""
    assert (
        shared_limit_conservative(
            DocumentedScopeStatus.VERIFIED_COMPLETE,
            ActionFlowScopeKind.ACCOUNT,
            frozenset(),
            True,
        )
        is ActionFlowResult.UNKNOWN
    )


def test_none_claimed_scope_with_full_proof_is_unknown() -> None:
    """(fail-closed) Nothing claimed => nothing to keep => UNKNOWN, never a silent default."""
    assert (
        shared_limit_conservative(
            DocumentedScopeStatus.VERIFIED_COMPLETE,
            None,
            _CREDIBLE_CONTAINING,
            True,
        )
        is ActionFlowResult.UNKNOWN
    )


def test_bare_string_status_is_not_the_verified_enum_member() -> None:
    """(truthy / identity seal) A raw ``"VERIFIED_COMPLETE"`` string is not the enum member."""
    verdict = shared_limit_conservative(
        "VERIFIED_COMPLETE",
        ActionFlowScopeKind.ACCOUNT,
        _CREDIBLE_CONTAINING,
        True,
    )
    assert verdict is ActionFlowScopeKind.GLOBAL


@given(credible=SCOPE_SETS, evidence=st.sampled_from([True, False, None]))
def test_shared_limit_is_never_narrower_than_the_rule_demands(
    credible: frozenset[ActionFlowScopeKind], evidence: bool | None
) -> None:
    """(property) Undocumented scope always yields the broadest member, or UNKNOWN when ∅."""
    verdict = shared_limit_conservative(
        DocumentedScopeStatus.INCOMPLETE,
        ActionFlowScopeKind.ACCOUNT,
        credible,
        evidence,
    )
    if not credible:
        assert verdict is ActionFlowResult.UNKNOWN
    else:
        assert verdict is broadest_scope(credible)


# ---------------------------------------------------------------------------
# envelope_not_enlarged (§8 line 248 — the "enlarge-envelope" forbidden verb)
# ---------------------------------------------------------------------------


def test_within_envelope_from_the_injected_source_passes() -> None:
    """(canary +) A requested limit at or below the injected envelope maximum => True."""
    assert (
        envelope_not_enlarged(
            requested_limit=limit_vector(magnitude=Decimal("50")),
            injected_envelope_max=limit_vector(magnitude=Decimal("100")),
            limit_source_is_injected_envelope=True,
        )
        is True
    )


def test_enlarging_the_envelope_is_rejected() -> None:
    """(canary 'enlarge-envelope' §8:248) A requested limit above the maximum => False."""
    assert (
        envelope_not_enlarged(
            requested_limit=limit_vector(magnitude=Decimal("101")),
            injected_envelope_max=limit_vector(magnitude=Decimal("100")),
            limit_source_is_injected_envelope=True,
        )
        is False
    )


def test_non_envelope_limit_source_is_rejected() -> None:
    """(canary - §8:248) A runtime / broker / model limit source => False; unknown too."""
    for source in (False, None):
        assert (
            envelope_not_enlarged(
                requested_limit=limit_vector(magnitude=Decimal("1")),
                injected_envelope_max=limit_vector(magnitude=Decimal("100")),
                limit_source_is_injected_envelope=source,
            )
            is False
        )


def test_absent_envelope_fails_closed() -> None:
    """(fail-closed) No injected envelope => nothing to compare against => False."""
    assert (
        envelope_not_enlarged(
            requested_limit=limit_vector(),
            injected_envelope_max=None,
            limit_source_is_injected_envelope=True,
        )
        is False
    )


def test_unknown_dimension_in_the_requested_limit_fails_closed() -> None:
    """(§2.2-4) An unenumerated (non-afg) dimension id fails closed, never unbounded."""
    alien = CapacityVector(
        components=(
            CapacityComponent(dimension_id="GROSS_NOTIONAL", magnitude=Decimal("1")),
        )
    )
    assert (
        envelope_not_enlarged(
            requested_limit=alien,
            injected_envelope_max=CapacityVector(
                components=(
                    CapacityComponent(
                        dimension_id="GROSS_NOTIONAL", magnitude=Decimal("100")
                    ),
                )
            ),
            limit_source_is_injected_envelope=True,
        )
        is False
    )


def test_none_magnitude_in_the_requested_limit_fails_closed() -> None:
    """(∅ §4.7 row 6) A ``None`` requested magnitude => False, never assume-within."""
    assert (
        envelope_not_enlarged(
            requested_limit=limit_vector(magnitude=None),
            injected_envelope_max=limit_vector(magnitude=Decimal("100")),
            limit_source_is_injected_envelope=True,
        )
        is False
    )


def test_empty_requested_limit_declares_zero_headroom_not_a_wildcard() -> None:
    """(documented interpretation) An empty requested limit enlarges nothing — but only
    after the positive source gate, and a caller's empty *requested scope* is denied
    separately in :func:`~tos.afg.action_flow_decision` (§4.7 row 3)."""
    assert (
        envelope_not_enlarged(
            requested_limit=CapacityVector(),
            injected_envelope_max=limit_vector(),
            limit_source_is_injected_envelope=True,
        )
        is True
    )
    # ...and it is still gated by the source: an unproven source fails closed.
    assert (
        envelope_not_enlarged(
            requested_limit=CapacityVector(),
            injected_envelope_max=limit_vector(),
            limit_source_is_injected_envelope=None,
        )
        is False
    )


def test_dimension_absent_from_the_envelope_fails_closed() -> None:
    """(fail-closed) A requested dimension the envelope does not declare => False."""
    assert (
        envelope_not_enlarged(
            requested_limit=limit_vector(
                dimension_id=BROKER_REQUEST_DIM, magnitude=Decimal("1")
            ),
            injected_envelope_max=limit_vector(
                dimension_id="QUEUE", magnitude=Decimal("100")
            ),
            limit_source_is_injected_envelope=True,
        )
        is False
    )
