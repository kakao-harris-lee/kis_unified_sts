"""hag predicate-only §6 predicates (design #20 §6.1-§6.6/§7) — SoD, human HALT, delegation,
compromise, governed-single-operator variant, operator config/authz.

These author the L1-decidable substrate but close **no** HAG-EV (≥ EV-L2 fault injection /
adversarial / +Security residue, §1). Regime tag: predicate / model substrate only;
HAG-EV-003/005/008/009/013-018 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.hag import (
    ApprovalScope,
    ConflictRole,
    EffectiveControlEdge,
    HumanAuthorityEffect,
    HumanDelegationRecord,
    HumanHaltCommand,
    RoleAssignment,
    RoleGrant,
    compromise_fails_closed,
    degraded_path_no_permissive,
    delegation_bounded_nontransitive,
    human_halt_monotonic_restrictive,
    operator_config_authz_error_fail_closed,
    separation_of_duties_satisfied,
    variant_pre_declared_exact_scope,
)

from ._hag_strategies import SCHEME, clean_graph

# ---------------------------------------------------------------------------
# §6.1 — separation of duties over effective principals (HAG-EV-003)
# ---------------------------------------------------------------------------


def test_sod_rejects_forbidden_pair_on_one_person() -> None:
    """(§12; HAG-INV-003) One person holding a forbidden pair (proposer + approver) fails."""
    graph = clean_graph(principal_ids=("alice", "bob"))
    conflicted = RoleAssignment(
        grants=(
            RoleGrant(principal_id="alice", role=ConflictRole.TRADING_PROPOSER),
            RoleGrant(principal_id="alice", role=ConflictRole.TRADE_APPROVER),
        )
    )
    assert separation_of_duties_satisfied(conflicted, graph) is False
    # …but the SAME two roles across two distinct people is fine.
    separated = RoleAssignment(
        grants=(
            RoleGrant(principal_id="alice", role=ConflictRole.TRADING_PROPOSER),
            RoleGrant(principal_id="bob", role=ConflictRole.TRADE_APPROVER),
        )
    )
    assert separation_of_duties_satisfied(separated, graph) is True


def test_sod_collapses_two_accounts_before_checking() -> None:
    """(§3.5) Two accounts of one person collapse, so a 'split' forbidden pair is still caught."""
    graph = clean_graph(
        principal_ids=("alice-a", "alice-b"),
        edges=(
            EffectiveControlEdge(source="alice-a", target="alice-b", resolved=None),
        ),
    )
    # The proposer + approver look like two accounts, but collapse to one effective person.
    split = RoleAssignment(
        grants=(
            RoleGrant(principal_id="alice-a", role=ConflictRole.TRADING_PROPOSER),
            RoleGrant(principal_id="alice-b", role=ConflictRole.TRADE_APPROVER),
        )
    )
    assert separation_of_duties_satisfied(split, graph) is False


def test_sod_unrepresented_principal_denies() -> None:
    """(MAJOR-2 §5.1 (vii)) A grant to a principal not in the graph denies."""
    graph = clean_graph(principal_ids=("alice",))
    grant = RoleAssignment(
        grants=(RoleGrant(principal_id="ghost", role=ConflictRole.TRADE_APPROVER),)
    )
    assert separation_of_duties_satisfied(grant, graph) is False


# ---------------------------------------------------------------------------
# §6.2 — human HALT monotonic-restrictive + degraded no-permissive (HAG-EV-005)
# ---------------------------------------------------------------------------


def _halt(
    command_id: str = "halt-1", restrictive_generation: int | None = 5
) -> HumanHaltCommand:
    return HumanHaltCommand.issue(
        scheme=SCHEME,
        command_id=command_id,
        principal_id="alice",
        restrictive_generation=restrictive_generation,
    )


def test_halt_monotonic_requires_strictly_advancing_generation() -> None:
    """(§15 line 410) The restrictive generation must strictly advance; a non-advance fails."""
    command = _halt(restrictive_generation=5)
    assert human_halt_monotonic_restrictive(command, None) is True  # first HALT
    assert human_halt_monotonic_restrictive(command, 4) is True  # 5 > 4 advances
    assert (
        human_halt_monotonic_restrictive(command, 5) is False
    )  # not strictly advancing
    assert human_halt_monotonic_restrictive(command, 6) is False  # regresses
    assert human_halt_monotonic_restrictive(None, 1) is False


def test_degraded_path_admits_restrictive_but_never_permissive() -> None:
    """(§15 line 417) A degraded-path restrictive latch is admitted; a permissive command never is."""
    command = _halt()
    assert (
        degraded_path_no_permissive(command, safety_commit_log_available=False) is True
    )
    assert (
        degraded_path_no_permissive(command, safety_commit_log_available=True) is True
    )
    assert degraded_path_no_permissive(None, safety_commit_log_available=False) is False
    # A smuggled permissive effect (via model_construct) is caught by the defence-in-depth check.
    permissive_effect = HumanAuthorityEffect.model_construct(re_arms=True)
    smuggled = command.model_copy(update={"human_authority_effect": permissive_effect})
    assert (
        degraded_path_no_permissive(smuggled, safety_commit_log_available=False)
        is False
    )


# ---------------------------------------------------------------------------
# §6.3 — delegation bounded + non-transitive (HAG-EV-008)
# ---------------------------------------------------------------------------


def test_delegation_bounded_nontransitive_positive_and_negatives() -> None:
    """(§13; HAG-INV-009) A bounded, non-transitive, within-authority delegation of distinct persons passes."""
    graph = clean_graph(principal_ids=("grantor", "delegate"))
    grantor_roles = frozenset({ConflictRole.TRADE_APPROVER, ConflictRole.LIVE_ARMER})
    ok = HumanDelegationRecord.issue(
        scheme=SCHEME,
        delegation_id="del-1",
        grantor_principal="grantor",
        delegate_principal="delegate",
        role=ConflictRole.TRADE_APPROVER,
        transitive=False,
        delegation_generation=1,
    )
    assert delegation_bounded_nontransitive(ok, grantor_roles, graph) is True
    # Transitive => rejected.
    transitive = ok.model_copy(update={"transitive": True})
    assert delegation_bounded_nontransitive(transitive, grantor_roles, graph) is False
    # Role beyond the grantor's authority => rejected.
    beyond = ok.model_copy(update={"role": ConflictRole.POLICY_ADMIN})
    assert delegation_bounded_nontransitive(beyond, grantor_roles, graph) is False


def test_delegation_same_effective_person_rejected() -> None:
    """(§5.1) If grantor and delegate collapse to one person, they cannot count independently."""
    graph = clean_graph(
        principal_ids=("grantor", "delegate"),
        edges=(
            EffectiveControlEdge(source="grantor", target="delegate", resolved=None),
        ),
    )
    grantor_roles = frozenset({ConflictRole.TRADE_APPROVER})
    same_person = HumanDelegationRecord.issue(
        scheme=SCHEME,
        delegation_id="del-1",
        grantor_principal="grantor",
        delegate_principal="delegate",
        role=ConflictRole.TRADE_APPROVER,
        transitive=False,
        delegation_generation=1,
    )
    assert delegation_bounded_nontransitive(same_person, grantor_roles, graph) is False


# ---------------------------------------------------------------------------
# §6.4 — compromise fails closed (HAG-EV-009)
# ---------------------------------------------------------------------------


def test_compromise_fails_closed_containment() -> None:
    """(§19; HAG-INV-010) A suspected compromise requires full containment; unknown is treated as suspected."""
    # No compromise => trivially satisfied (nothing to contain).
    assert (
        compromise_fails_closed(
            compromise_suspected=False,
            pending_authority_invalidated=None,
            scope_restricted_to_narrowest=None,
            economic_effect_preserved=None,
        )
        is True
    )
    # Suspected, full containment => satisfied.
    assert (
        compromise_fails_closed(
            compromise_suspected=True,
            pending_authority_invalidated=True,
            scope_restricted_to_narrowest=True,
            economic_effect_preserved=True,
        )
        is True
    )
    # Suspected, missing a containment step => fails.
    assert (
        compromise_fails_closed(
            compromise_suspected=True,
            pending_authority_invalidated=False,
            scope_restricted_to_narrowest=True,
            economic_effect_preserved=True,
        )
        is False
    )
    # Unknown (None) is treated as suspected => must contain fully.
    assert (
        compromise_fails_closed(
            compromise_suspected=None,
            pending_authority_invalidated=None,
            scope_restricted_to_narrowest=None,
            economic_effect_preserved=None,
        )
        is False
    )


# ---------------------------------------------------------------------------
# §6.5/§6.6 — governed single-operator variant + operator config/authz (HAG-EV-013-018)
# ---------------------------------------------------------------------------


def _scope(instruments: frozenset[str]) -> ApprovalScope:
    return ApprovalScope(
        instruments=instruments,
        accounts=frozenset({"ACCT"}),
        venues=frozenset({"V"}),
        environments=frozenset({"paper"}),
        action_classes=frozenset({"NEW_LONG"}),
        sides=frozenset({"BUY"}),
        routes=frozenset({"R"}),
    )


def test_variant_pre_declared_exact_scope() -> None:
    """(§17.1.1; HAG-INV-015) A variant is admissible only when pre-declared with the exact scope."""
    declared = _scope(frozenset({"AAA"}))
    # Exact match => admissible.
    assert (
        variant_pre_declared_exact_scope(True, declared, _scope(frozenset({"AAA"})))
        is True
    )
    # Not declared => denial.
    assert variant_pre_declared_exact_scope(None, declared, declared) is False
    assert variant_pre_declared_exact_scope(False, declared, declared) is False
    # Ad-hoc expansion at re-arm time => denial (no selection / expansion).
    assert (
        variant_pre_declared_exact_scope(
            True, declared, _scope(frozenset({"AAA", "BBB"}))
        )
        is False
    )
    # A None scope dimension => fail-closed.
    assert variant_pre_declared_exact_scope(True, declared, None) is False


def test_operator_config_authz_error_fail_closed() -> None:
    """(§17.1; HAG-INV-015) Missing declaration / scope mismatch / authz error => denial."""
    assert operator_config_authz_error_fail_closed(True, True, True) is True
    assert operator_config_authz_error_fail_closed(None, True, True) is False
    assert operator_config_authz_error_fail_closed(True, False, True) is False
    assert operator_config_authz_error_fail_closed(True, True, None) is False
