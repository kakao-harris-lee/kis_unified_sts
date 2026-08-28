"""venue records — id ⊥ digest, substitution detection, all-false authority (design #19 §2.1/§2.4).

Regime tag: predicate / model substrate only; VTG-EV-006 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
from tos.venue import (
    ActionClass,
    ArtifactStatus,
    OrderAdmissibilityResult,
    RecordPairKind,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueGateAuthorityEffect,
    classify_record_pair,
)
from tos.venue._base import ArtifactIntegrityError

from ._venue_strategies import (
    SCHEME,
    clean_decision,
    clean_policy,
    clean_snapshot,
)

# ---------------------------------------------------------------------------
# id ⊥ digest — the three core artifacts are IndependentIdArtifact
# ---------------------------------------------------------------------------


def test_three_core_artifacts_are_id_independent() -> None:
    """(§2.1) policy / snapshot / decision are issued-identity (id != f(digest))."""
    policy = clean_policy()
    snapshot = clean_snapshot()
    decision = clean_decision()
    # The id is separately injected, NOT derived from the digest.
    assert policy.policy_id == "venue-policy-1"
    assert policy.canonical_digest is not None
    assert policy.policy_id != policy.canonical_digest
    assert snapshot.snapshot_id != snapshot.canonical_digest
    assert decision.decision_id != decision.canonical_digest


def test_issued_artifact_requires_concrete_id() -> None:
    """(canonical §3.1) An ISSUED artifact with a null id is unconstructable."""
    with pytest.raises((ArtifactIntegrityError, ValueError)):
        # Force ISSUED status with a null id — the independent-id validator rejects it.
        VenueConstraintPolicy(
            policy_id=None,
            policy_generation=3,
            canonical_digest="x",
            status=ArtifactStatus.ISSUED,
            canonicalization_version=SCHEME.version,
        )


def test_digest_covers_decision_result_substitution_is_detectable() -> None:
    """(§14 line 342-343) A same-id / different-result decision is a CRITICAL_CONFLICT."""
    admissible = clean_decision(result=OrderAdmissibilityResult.ADMISSIBLE)
    # Same decision_id, different bytes (INADMISSIBLE) — a forged substitution.
    inadmissible = clean_decision(result=OrderAdmissibilityResult.INADMISSIBLE)
    assert admissible.decision_id == inadmissible.decision_id
    assert admissible.canonical_digest != inadmissible.canonical_digest
    kind = classify_record_pair(
        admissible.decision_id,
        admissible.canonical_digest,
        inadmissible.decision_id,
        inadmissible.canonical_digest,
    )
    assert kind is RecordPairKind.CRITICAL_CONFLICT


def test_same_content_decision_is_idempotent_dup() -> None:
    """(§2.1) A same-id / same-bytes decision is an idempotent duplicate, not a conflict."""
    d1 = clean_decision()
    d2 = clean_decision()
    assert d1.canonical_digest == d2.canonical_digest
    kind = classify_record_pair(
        d1.decision_id, d1.canonical_digest, d2.decision_id, d2.canonical_digest
    )
    assert kind is RecordPairKind.IDEMPOTENT_DUP


# ---------------------------------------------------------------------------
# all-false VenueGateAuthorityEffect (§2.2(4) / §6.7 / VTG-INV-011)
# ---------------------------------------------------------------------------


def test_default_authority_effect_is_all_false() -> None:
    """(VTG-INV-011 line 189) The default authority effect has every flag False."""
    effect = VenueGateAuthorityEffect()
    assert effect.approves is False
    assert effect.mutates_capacity is False
    assert effect.issues_authority is False
    assert effect.classifies_protection is False
    assert effect.transmits is False
    assert effect.clears_halt is False
    assert effect.rearms is False


def test_any_true_authority_flag_is_unconstructable() -> None:
    """(VTG-INV-011) Any True authority flag makes the effect unconstructable."""
    for flag in (
        "approves",
        "mutates_capacity",
        "issues_authority",
        "classifies_protection",
        "transmits",
        "clears_halt",
        "rearms",
    ):
        with pytest.raises((ArtifactIntegrityError, ValueError)):
            VenueGateAuthorityEffect(**{flag: True})


def test_decision_carries_all_false_authority() -> None:
    """(§14 line 340-341) An issued decision carries an all-false authority effect."""
    decision = clean_decision()
    assert decision.authority_effect.approves is False
    assert decision.authority_effect.transmits is False
    assert decision.authority_effect.rearms is False


# ---------------------------------------------------------------------------
# frozen / extra-forbid discipline
# ---------------------------------------------------------------------------


def test_records_are_frozen_and_extra_forbid() -> None:
    """(§2.0) Models are frozen (no mutation) and forbid unknown fields."""
    decision = clean_decision()
    with pytest.raises((ValueError, TypeError)):
        decision.result = OrderAdmissibilityResult.INADMISSIBLE  # type: ignore[misc]
    with pytest.raises((ValueError, TypeError)):
        VenueConstraintSnapshot(snapshot_id="x", unknown_field="y")  # type: ignore[call-arg]


def test_admitting_phases_for_unenumerated_action_is_none() -> None:
    """(§5.1 fail-closed) An unenumerated action returns None (restrictive at the predicate)."""
    policy = clean_policy(action=ActionClass.NEW_LONG)
    assert policy.admitting_phases_for(ActionClass.NEW_LONG) == frozenset(
        {"continuous_trading"}
    )
    assert policy.admitting_phases_for(ActionClass.NEW_SHORT) is None


def test_material_change_unknown_materiality_is_material() -> None:
    """(§5.8 line 139) Unknown materiality (None) is treated as material."""
    from tos.venue import MaterialConstraintChange

    assert MaterialConstraintChange(material=None).is_material() is True
    assert MaterialConstraintChange(material=True).is_material() is True
    assert MaterialConstraintChange(material=False).is_material() is False
