"""hag core §5 predicates (design #20 §5.2-§5.8/§7) — exact binding, single-use, break-glass,
protective-proposal-only, dual-control, continuity/non-revival, replay.

Regime tag: predicate / model substrate only; HAG-EV-002/004/006/007/010/011/012 substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.hag import (
    ApprovalLifecycleState,
    AuthorityClass,
    HumanAuthorityEffect,
    approval_binding_exact,
    approval_expiry_preserves_economic_effect,
    break_glass_direction_restrictive,
    human_authority_effect_separated,
    human_authority_replay_reconstructs,
    human_protective_request_proposal_only,
    lifecycle_transition_legal,
    material_change_invalidates,
    no_automatic_rearm,
    stale_replayed_rejected,
)

from ._hag_strategies import clean_attestation, clean_request

# ---------------------------------------------------------------------------
# §5.2 — exact approval context binding + material change (HAG-EV-002)
# ---------------------------------------------------------------------------


def test_approval_binding_exact_matches_request_digest() -> None:
    """(§5.2) An attestation binding the request's exact digest is exact; a mismatch fails closed."""
    request = clean_request()
    bound = clean_attestation(
        attestation_id="a1",
        principal_id="alice",
        request_digest=request.canonical_digest,
    )
    wrong = clean_attestation(
        attestation_id="a2", principal_id="alice", request_digest="some-other-digest"
    )
    assert approval_binding_exact(request, bound) is True
    assert approval_binding_exact(request, wrong) is False


def test_material_change_invalidates_on_digest_drift() -> None:
    """(§1 line 30 / HAG-INV-008) A changed context digest invalidates a pre-consumption approval."""
    request = clean_request()
    assert material_change_invalidates(request, request.canonical_digest) is False
    assert material_change_invalidates(request, "changed-context") is True
    assert material_change_invalidates(request, None) is True
    assert material_change_invalidates(None, "x") is True


# ---------------------------------------------------------------------------
# §5.3 — stale/replayed rejection + lifecycle transitions (HAG-EV-004)
# ---------------------------------------------------------------------------


def test_stale_replayed_rejected_terminal_and_replay() -> None:
    """(§5.3) Terminal states / replays / policy-mismatch reject; a live progress state passes."""
    # A live progress state, not replayed, policy matches => NOT rejected.
    assert (
        stale_replayed_rejected(
            ApprovalLifecycleState.QUORUM_SATISFIED, replayed=False, policy_matches=True
        )
        is False
    )
    # Terminal state => reject.
    assert (
        stale_replayed_rejected(
            ApprovalLifecycleState.EXPIRED, replayed=False, policy_matches=True
        )
        is True
    )
    assert (
        stale_replayed_rejected(
            ApprovalLifecycleState.CONSUMED, replayed=False, policy_matches=True
        )
        is True
    )
    # Replay => reject even in a progress state.
    assert (
        stale_replayed_rejected(
            ApprovalLifecycleState.QUORUM_SATISFIED, replayed=True, policy_matches=True
        )
        is True
    )
    # Policy mismatch / unknown => reject (fail-closed).
    assert (
        stale_replayed_rejected(
            ApprovalLifecycleState.QUORUM_SATISFIED, replayed=False, policy_matches=None
        )
        is True
    )
    # None state => reject.
    assert stale_replayed_rejected(None, replayed=False, policy_matches=True) is True


def test_lifecycle_transition_only_quorum_to_consumed() -> None:
    """(§18 line 521) Only QUORUM_SATISFIED -> CONSUMED; terminals have no permissive exit."""
    assert (
        lifecycle_transition_legal(
            ApprovalLifecycleState.QUORUM_SATISFIED, ApprovalLifecycleState.CONSUMED
        )
        is True
    )
    assert (
        lifecycle_transition_legal(
            ApprovalLifecycleState.ATTESTING, ApprovalLifecycleState.CONSUMED
        )
        is False
    )
    # No permissive return from a terminal state.
    assert (
        lifecycle_transition_legal(
            ApprovalLifecycleState.EXPIRED, ApprovalLifecycleState.REVIEWABLE
        )
        is False
    )
    assert (
        lifecycle_transition_legal(
            ApprovalLifecycleState.CONSUMED, ApprovalLifecycleState.QUORUM_SATISFIED
        )
        is False
    )
    # A normal forward progress arrow is legal.
    assert (
        lifecycle_transition_legal(
            ApprovalLifecycleState.REQUESTED, ApprovalLifecycleState.REVIEWABLE
        )
        is True
    )
    assert lifecycle_transition_legal(None, ApprovalLifecycleState.REVIEWABLE) is False


def test_lifecycle_table_verbatim_aligned_with_adr_18() -> None:  # MINOR-1
    """(§18 line 511-518 verbatim) QUORUM_SATISFIED->DENIED legal (514); SUPERSEDED only from QUORUM_SATISFIED (518)."""
    # (i) §18 line 514 — a QUORUM_SATISFIED set may still be DENIED ("a later APPROVE does not
    #     erase a retained denial").
    assert (
        lifecycle_transition_legal(
            ApprovalLifecycleState.QUORUM_SATISFIED, ApprovalLifecycleState.DENIED
        )
        is True
    )
    # (ii) §18 line 518 — SUPERSEDED is reachable ONLY from QUORUM_SATISFIED.
    assert (
        lifecycle_transition_legal(
            ApprovalLifecycleState.QUORUM_SATISFIED, ApprovalLifecycleState.SUPERSEDED
        )
        is True
    )
    for early in (
        ApprovalLifecycleState.REQUESTED,
        ApprovalLifecycleState.REVIEWABLE,
        ApprovalLifecycleState.ATTESTING,
    ):
        assert (
            lifecycle_transition_legal(early, ApprovalLifecycleState.SUPERSEDED)
            is False
        ), f"{early} must NOT reach SUPERSEDED (ADR §18 line 518)"


# ---------------------------------------------------------------------------
# §5.4 — break-glass directional confinement (HAG-EV-006)
# ---------------------------------------------------------------------------


def test_break_glass_only_restrictive_classes() -> None:
    """(§7/§16 line 425; HAG-INV-006) Only HALT / NARROW / REQUEST_PROTECTIVE pass; all else fails."""
    for restrictive in (
        AuthorityClass.HALT,
        AuthorityClass.NARROW,
        AuthorityClass.REQUEST_PROTECTIVE,
    ):
        assert break_glass_direction_restrictive(restrictive) is True
    for increasing in (
        AuthorityClass.APPROVE_PROFILE_OR_ENVELOPE,
        AuthorityClass.APPROVE_REARM,
        AuthorityClass.ACCEPT_RESIDUAL_RISK,
        AuthorityClass.CAPACITY_MUTATION,
        AuthorityClass.TRANSMIT,
    ):
        assert break_glass_direction_restrictive(increasing) is False
    # None (unproven direction => MAY_INCREASE, §7 line 249) => False.
    assert break_glass_direction_restrictive(None) is False


# ---------------------------------------------------------------------------
# §5.5 — human protective request is proposal-only (HAG-EV-007)
# ---------------------------------------------------------------------------


def test_human_protective_request_needs_all_three_verdicts() -> None:
    """(§16; HAG-INV-007) A protective request proceeds only on classification + capacity + egress."""
    request = clean_request(request_type=AuthorityClass.REQUEST_PROTECTIVE)
    # All three injected verdicts positive => proceed.
    assert (
        human_protective_request_proposal_only(
            request,
            protective_classification_admissible=True,
            capacity_authorized=True,
            egress_verified=True,
        )
        is True
    )
    # Any missing verdict fails closed.
    assert (
        human_protective_request_proposal_only(
            request,
            protective_classification_admissible=None,
            capacity_authorized=True,
            egress_verified=True,
        )
        is False
    )
    assert (
        human_protective_request_proposal_only(
            request,
            protective_classification_admissible=True,
            capacity_authorized=False,
            egress_verified=True,
        )
        is False
    )
    # A non-protective request class never proceeds via this predicate (the label ↛ classification).
    non_protective = clean_request(request_type=AuthorityClass.CAPACITY_MUTATION)
    assert (
        human_protective_request_proposal_only(
            non_protective,
            protective_classification_admissible=True,
            capacity_authorized=True,
            egress_verified=True,
        )
        is False
    )


# ---------------------------------------------------------------------------
# §5.7 — economic continuity + non-revival (HAG-EV-011)
# ---------------------------------------------------------------------------


def test_approval_expiry_preserves_economic_effect_unconditionally() -> None:
    """(HAG-INV-012) Approval expiry never mutates an economic effect — unconditional True."""
    assert approval_expiry_preserves_economic_effect(None) is True
    assert approval_expiry_preserves_economic_effect({"expired": True}) is True


def test_no_automatic_rearm_under_any_recovery() -> None:
    """(HAG-INV-014) No recovery / timeout / restart auto-re-arms — unconditional True."""
    assert no_automatic_rearm() is True
    assert (
        no_automatic_rearm(
            health_recovered=True,
            timeout_elapsed=True,
            reconciliation_completed=True,
            leader_elected=True,
            restart_completed=True,
        )
        is True
    )


# ---------------------------------------------------------------------------
# §5.8 — replay reconstruction + evidence-is-not-authority (HAG-EV-012)
# ---------------------------------------------------------------------------


def test_replay_reconstructs_unless_critical_conflict() -> None:
    """(§22; HAG-AC-012) Replay reconstructs unless a same-id / different-bytes conflict exists."""
    consistent = [
        ("att-1", "digest-a"),
        ("att-2", "digest-b"),
        ("att-1", "digest-a"),  # idempotent duplicate — fine
    ]
    assert human_authority_replay_reconstructs(consistent) is True
    forged = [
        ("att-1", "digest-a"),
        ("att-1", "digest-DIFFERENT"),  # same id, different bytes — CRITICAL_CONFLICT
    ]
    assert human_authority_replay_reconstructs(forged) is False
    # Pre-issuance (null digest) records are skipped (NOT_COMPARABLE), never a false conflict.
    with_draft = [("att-1", None), ("att-1", "digest-a")]
    assert human_authority_replay_reconstructs(with_draft) is True


def test_evidence_is_not_authority_all_false_effect() -> None:
    """(§4.3/§22 line 596) A validated human-authority effect grants no authority; None fails closed."""
    assert human_authority_effect_separated(HumanAuthorityEffect()) is True
    assert human_authority_effect_separated(None) is False


def test_model_construct_bypass_is_caught_by_defence_in_depth() -> None:
    """(§4.3 defence-in-depth) An unvalidated model_construct with a True flag is caught by the predicate."""
    # model_construct skips the validator — the consuming predicate must still reject it.
    smuggled = HumanAuthorityEffect.model_construct(re_arms=True)
    assert human_authority_effect_separated(smuggled) is False
