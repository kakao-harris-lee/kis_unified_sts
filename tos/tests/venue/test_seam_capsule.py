"""MANDATED test-only seam cross-check: venue -> capsule 3-Ref shape parity (design #19 §3.4(d)/§2.1/§7).

capsule owns the three Layer-2 reference schemas — ``VenueConstraintPolicyRef`` = {policy_id,
policy_generation, canonical_digest}, ``VenueConstraintSnapshotRef`` = {snapshot_id,
constraint_generation, canonical_digest}, ``OrderAdmissibilityDecisionRef`` = {decision_id,
canonical_digest} (``capsule/capsule.py:130-150``), carried by ``DecisionContextCapsule``
(``capsule.py:242-244``). venue owns the **full** artifacts and produces exactly those (id,
generation, digest) coordinates; capsule does not import ``tos.venue`` (sibling edge 0).

This file imports the real capsule Refs as a **test** to lock the coordinate parity — the
venue-produced coordinates fill the capsule Ref / capsule slots exactly. A test-only cross-import
is **not** a runtime package edge (§3.4(d)/§7.1).

Regime tag: predicate / model substrate only; VTG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.capsule import DecisionContextCapsule
from tos.capsule.capsule import (
    OrderAdmissibilityDecisionRef,
    VenueConstraintPolicyRef,
    VenueConstraintSnapshotRef,
)
from tos.venue import (
    order_admissibility_decision_ref_coordinates,
    venue_constraint_policy_ref_coordinates,
    venue_constraint_snapshot_ref_coordinates,
)

from ._venue_strategies import clean_decision, clean_policy, clean_snapshot


def test_policy_ref_coordinate_parity() -> None:
    """(seam, §2.1) venue policy coordinates fill the capsule VenueConstraintPolicyRef exactly."""
    policy = clean_policy()
    policy_id, generation, digest = venue_constraint_policy_ref_coordinates(policy)
    ref = VenueConstraintPolicyRef(
        policy_id=policy_id, policy_generation=generation, canonical_digest=digest
    )
    assert ref.policy_id == policy.policy_id
    assert ref.policy_generation == policy.policy_generation
    assert ref.canonical_digest == policy.canonical_digest


def test_snapshot_ref_coordinate_parity() -> None:
    """(seam, §2.1) venue snapshot coordinates fill the capsule VenueConstraintSnapshotRef exactly."""
    snapshot = clean_snapshot()
    snapshot_id, generation, digest = venue_constraint_snapshot_ref_coordinates(
        snapshot
    )
    ref = VenueConstraintSnapshotRef(
        snapshot_id=snapshot_id,
        constraint_generation=generation,
        canonical_digest=digest,
    )
    assert ref.snapshot_id == snapshot.snapshot_id
    assert ref.constraint_generation == snapshot.constraint_generation
    assert ref.canonical_digest == snapshot.canonical_digest


def test_decision_ref_coordinate_parity_no_generation() -> None:
    """(seam, §2.1) The decision Ref carries only (id, digest) — no generation coordinate."""
    decision = clean_decision()
    decision_id, digest = order_admissibility_decision_ref_coordinates(decision)
    ref = OrderAdmissibilityDecisionRef(
        decision_id=decision_id, canonical_digest=digest
    )
    assert ref.decision_id == decision.decision_id
    assert ref.canonical_digest == decision.canonical_digest
    # The Ref schema has exactly two fields (no generation) — parity with the producer pair.
    assert set(OrderAdmissibilityDecisionRef.model_fields) == {
        "decision_id",
        "canonical_digest",
    }


def test_decision_context_capsule_carries_the_three_refs() -> None:
    """(seam) DecisionContextCapsule carries all three venue Ref slots (capsule.py:242-244)."""
    fields = DecisionContextCapsule.model_fields
    assert "venue_constraint_policy" in fields
    assert "venue_constraint_snapshot" in fields
    assert "order_admissibility_decision" in fields


def test_venue_refs_fill_the_capsule_slots() -> None:
    """(seam positive) The venue-produced Refs are accepted into the capsule slots."""
    policy = clean_policy()
    snapshot = clean_snapshot()
    decision = clean_decision()
    pid, pgen, pdig = venue_constraint_policy_ref_coordinates(policy)
    sid, sgen, sdig = venue_constraint_snapshot_ref_coordinates(snapshot)
    did, ddig = order_admissibility_decision_ref_coordinates(decision)
    capsule = DecisionContextCapsule(
        venue_constraint_policy=VenueConstraintPolicyRef(
            policy_id=pid, policy_generation=pgen, canonical_digest=pdig
        ),
        venue_constraint_snapshot=VenueConstraintSnapshotRef(
            snapshot_id=sid, constraint_generation=sgen, canonical_digest=sdig
        ),
        order_admissibility_decision=OrderAdmissibilityDecisionRef(
            decision_id=did, canonical_digest=ddig
        ),
    )
    assert capsule.venue_constraint_policy.policy_id == policy.policy_id
    assert (
        capsule.venue_constraint_snapshot.constraint_generation
        == snapshot.constraint_generation
    )
    assert (
        capsule.order_admissibility_decision.canonical_digest
        == decision.canonical_digest
    )


def test_none_producers_yield_all_none_coordinates() -> None:
    """(seam, fail-closed) None artifacts produce all-None coordinate tuples."""
    assert venue_constraint_policy_ref_coordinates(None) == (None, None, None)
    assert venue_constraint_snapshot_ref_coordinates(None) == (None, None, None)
    assert order_admissibility_decision_ref_coordinates(None) == (None, None)
