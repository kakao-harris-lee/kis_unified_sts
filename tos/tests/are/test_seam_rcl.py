"""MANDATED test-only seam cross-check: are <-> rcl (design #13 §3.4/§0.4c; MAJOR-1).

are imports the rcl ``CapacityVector`` **type** at runtime (the one allowed sibling edge); it
does NOT re-author rcl's binding / capacity arithmetic. This file imports the rcl
``GrantDecisionRef`` / ``RclAuthorityEffect`` / ``grant_authorizes_exact_request`` consumers as
a **test** to lock (a) the forward-only decision-content ref seam, (b) the all-false authority
isomorphism, and (c) the type-level dominance (the final ``AdverseIncrement[s,d]`` IS the rcl
``CapacityVector`` rcl commits).

A test-only cross-import is NOT a runtime package edge for the consumer seam (design #13
§3.4/§7.1); the ``CapacityVector`` type edge is the single sanctioned ``are -> rcl`` import.
"""

from __future__ import annotations

import tos.are as are
from tos.are import AggregateRiskAuthorityEffect, decision_content_ref
from tos.canonical import ArtifactIntegrityError
from tos.rcl import (
    CapacityVector,
    CommittedReservation,
    GrantDecisionRef,
    RclAuthorityEffect,
)

from ._are_strategies import issue_decision


def test_are_content_ref_fills_grant_decision_ref() -> None:
    """(seam) are's forward-only content ref populates rcl GrantDecisionRef's separate fields."""
    decision = issue_decision()
    decision_id, generation, digest = decision_content_ref(decision)
    ref = GrantDecisionRef(
        decision_id=decision_id,
        decision_generation=generation,
        canonical_decision_digest=digest,
    )
    assert ref.decision_id == decision.decision_id
    assert ref.decision_generation == decision.decision_generation
    assert ref.canonical_decision_digest == decision.canonical_digest  # id ⊥ digest


def test_forward_only_are_supplies_no_reservation_binding() -> None:
    """(§16 non-cyclic) A grant built from are content alone (no reservation binding) is not authorized.

    are produces only ``decision_id`` / ``generation`` / ``digest``; it never reads back an rcl
    reservation result — so ``bound_reservation_*`` are ``None`` until rcl charges them
    post-commit, and ``grant_authorizes_exact_request`` fails closed. This is the code proof of
    the non-cyclic pipeline (design #13 §5.6).
    """
    from tos.rcl import grant_authorizes_exact_request

    decision_id, generation, digest = decision_content_ref(issue_decision())
    ref = GrantDecisionRef(
        decision_id=decision_id,
        decision_generation=generation,
        canonical_decision_digest=digest,
    )  # bound_reservation_revision / _digest / bound_generation all None (are supplies none)
    assert ref.bound_reservation_revision is None
    assert ref.bound_reservation_digest is None
    assert (
        grant_authorizes_exact_request(
            ref, CommittedReservation(), current_generation=1
        )
        is False
    )


def test_are_all_false_authority_is_isomorphic_to_rcl() -> None:
    """(ARE-INV-009) are's all-false authority effect matches rcl's — both reject any True flag."""
    are_effect = AggregateRiskAuthorityEffect()
    rcl_effect = RclAuthorityEffect()
    assert are.grants_no_authority(are_effect) is True
    # both are all-false and unconstructable with any True flag.
    for cls in (AggregateRiskAuthorityEffect, RclAuthorityEffect):
        raised = False
        try:
            cls(creates_capacity=True)  # type: ignore[call-arg]
        except (ArtifactIntegrityError, Exception):
            raised = True
        assert raised, f"{cls.__name__}(creates_capacity=True) must be unconstructable"
    assert rcl_effect.creates_capacity is False


def test_final_increment_is_the_rcl_capacity_vector_type() -> None:
    """(MAJOR-1 type-seal) are's final AdverseIncrement[s,d] is the exact rcl CapacityVector type.

    No self-authored vector, no reduction reducer — the increment the decision carries is the
    same type rcl commits (``CommitReservation.proposed_adverse_increment``), so dominance is
    sealed at the type level (design #13 §0.4c).
    """
    decision = issue_decision()
    assert isinstance(decision.adverse_increment, CapacityVector)
    assert (
        are.AggregateRiskDecision.model_fields["adverse_increment"].annotation
        is CapacityVector
    )
    # rcl's commit coordinate (``adverse_increment``) is the same type — an increment produced
    # here drops straight into rcl without a reduction reducer.
    reservation = CommittedReservation()
    assert isinstance(reservation.adverse_increment, CapacityVector)
    assert (
        CommittedReservation.model_fields["adverse_increment"].annotation
        is CapacityVector
    )
