"""∅-void both-ways canaries across the hag predicates (design #20 §4.7).

Every empty-input guard is checked in BOTH directions: the forbidden (vacuous-permissive)
direction fires, and the legitimate positive direction is NOT blocked. A vacuous-satisfied quorum
is a safety violation; a vacuous-rejected genuine quorum is an availability violation — both are
defects (#12 both-ways lesson).

Regime tag: predicate / model substrate only; HAG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.hag import (
    ApprovalScope,
    approval_binding_exact,
    approval_set_single_use,
    dual_control_effective_distinct,
    partial_rearm_scope_narrows,
    quorum_independence_satisfied,
    separation_of_duties_satisfied,
)

from ._hag_strategies import (
    clean_approval_set,
    clean_attestation,
    clean_graph,
    clean_request,
    clean_two_person_attestations,
)


def test_empty_approval_set_blocks_but_two_person_set_passes() -> None:
    """(∅ both-ways) ∅ attestations => 0 < N => reject; two distinct persons => pass."""
    graph = clean_graph(principal_ids=("alice", "bob"))
    assert quorum_independence_satisfied([], graph, 2, frozenset()) is False
    assert (
        quorum_independence_satisfied(
            clean_two_person_attestations(), graph, 2, frozenset()
        )
        is True
    )


def test_empty_scope_narrowing_is_lawful_but_none_dimension_fails() -> None:
    """(∅ both-ways, §4.7) ∅ new scope ⊆ prior is a lawful de-authorization; a None dimension fails."""
    prior = ApprovalScope(
        instruments=frozenset({"AAA", "BBB"}),
        accounts=frozenset({"ACCT"}),
        venues=frozenset({"V"}),
        environments=frozenset({"paper"}),
        action_classes=frozenset({"NEW_LONG"}),
        sides=frozenset({"BUY"}),
        routes=frozenset({"R"}),
    )
    # ∅ on every dimension is a full de-authorization (∅ ⊆ prior) — lawful.
    empty = ApprovalScope(
        instruments=frozenset(),
        accounts=frozenset(),
        venues=frozenset(),
        environments=frozenset(),
        action_classes=frozenset(),
        sides=frozenset(),
        routes=frozenset(),
    )
    assert partial_rearm_scope_narrows(prior, empty) is True
    # A None dimension is UNKNOWN => fail-closed (never a permissive default).
    unknown = empty.model_copy(update={"instruments": None})
    assert partial_rearm_scope_narrows(prior, unknown) is False
    # A widening on any dimension is rejected.
    wider = prior.model_copy(update={"instruments": frozenset({"AAA", "BBB", "CCC"})})
    assert partial_rearm_scope_narrows(prior, wider) is False


def test_none_inputs_block_but_clean_inputs_pass() -> None:
    """(∅ both-ways) None request / attestation / consumption / assignment fail closed; clean ones pass."""
    # approval binding
    request = clean_request()
    att = clean_attestation(
        attestation_id="a1",
        principal_id="alice",
        request_digest=request.canonical_digest,
    )
    assert approval_binding_exact(None, att) is False
    assert approval_binding_exact(request, None) is False
    assert approval_binding_exact(request, att) is True
    # single-use consumption
    assert approval_set_single_use(None, []) is False


def test_empty_role_assignment_has_no_conflict_but_unresolved_graph_denies() -> None:
    """(∅ both-ways) ∅ roster holds no forbidden pair (True); an unresolved graph denies (False)."""
    from tos.hag import RoleAssignment

    resolved = clean_graph(principal_ids=("alice",))
    unresolved = clean_graph(principal_ids=("alice",), unresolved_control=None)
    assert separation_of_duties_satisfied(RoleAssignment(grants=()), resolved) is True
    assert (
        separation_of_duties_satisfied(RoleAssignment(grants=()), unresolved) is False
    )


def test_dual_control_empty_and_single_reject_but_two_pass() -> None:
    """(∅ / 1-person both-ways) ∅ and single attestation fail dual-control; two distinct pass."""
    graph = clean_graph(principal_ids=("alice", "bob"))
    assert dual_control_effective_distinct([], graph) is False
    single = (clean_attestation(attestation_id="a1", principal_id="alice"),)
    assert dual_control_effective_distinct(single, graph) is False
    assert (
        dual_control_effective_distinct(clean_two_person_attestations(), graph) is True
    )


def test_approval_set_reconsumption_blocks_but_first_use_passes() -> None:
    """(∅ / replay both-ways) First single-use consumption passes; a re-consumption of the set fails."""
    from tos.hag import ApprovalSetConsumptionRecord

    from ._hag_strategies import SCHEME

    first = ApprovalSetConsumptionRecord.issue(
        scheme=SCHEME,
        consumption_id="con-1",
        approval_set_digest="set-digest",
        single_use=True,
        consumed_generation=1,
    )
    assert approval_set_single_use(first, []) is True
    # A second consumption of the SAME set digest is rejected (single-use spent).
    second = ApprovalSetConsumptionRecord.issue(
        scheme=SCHEME,
        consumption_id="con-2",
        approval_set_digest="set-digest",
        single_use=True,
        consumed_generation=2,
    )
    assert approval_set_single_use(second, [first]) is False


def test_clean_approval_set_is_genuinely_bound() -> None:
    """(#8 fixture discipline) The clean approval set is genuinely digest-bound (not a shortcut)."""
    approval_set = clean_approval_set()
    assert approval_set.canonical_digest is not None
    assert approval_set.bound_request_digest == "req-digest"
    assert len(approval_set.attestations) == 2
