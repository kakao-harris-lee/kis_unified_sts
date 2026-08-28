"""Predicate-only evidence surfaces (design #4 §5.3/§2.5B/§4.6/§3.5/§2.2/§2.0).

EV-L1 predicate-only (no "EV-L1-complete" claim, §7 discipline): causal closure
(ERI-EV-001), redaction preservation (ERI-EV-009), repair non-revival
(ERI-EV-012), plus the always-on authority-absence invariant (ERI-INV-001/014)
and the EIP / receipt binding + substitution-rejection predicates.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.evidence import (
    CausalLink,
    EdgeType,
    GapStatus,
    PreservedProperty,
    RedactionProfile,
    causal_chain_complete,
    corrected_by,
    eip_binding_ok,
    grants_no_authority,
    receipt_binds_record,
    receipt_substitution_rejected,
    redaction_preserves_digest,
    redaction_profile_valid,
    repair_preserves_uncertainty,
)
from tos.evidence.elements import RemainingUncertainty
from tos.evidence.gap import GapRepair

from ._evidence_strategies import (
    issue_eip,
    issue_envelope,
    issue_receipt,
    issue_replay,
    make_gap,
)

# ===========================================================================
# ERI-EV-001 — causal closure / gap-on-omission (predicate-only, §5.3)
# ===========================================================================


def _env_with_links(*links: CausalLink):
    from tos.evidence.envelope import Causality

    return issue_envelope(causality=Causality(correlation_id="c", causal_links=links))


def test_causal_chain_complete_when_parent_present() -> None:
    """A required parent edge whose target is known is a complete chain (§5.3)."""
    link = CausalLink(edge_type=EdgeType.INTENT, target_id="er-0", target_digest="d0")
    env = _env_with_links(link)
    assert causal_chain_complete(
        env,
        required_parent_edge_types=[EdgeType.INTENT],
        known_targets=[("er-0", "d0")],
    )


def test_missing_required_parent_is_incomplete() -> None:
    """A missing required parent edge type is an incomplete chain => gap (§12 326)."""
    env = _env_with_links()
    assert not causal_chain_complete(
        env, required_parent_edge_types=[EdgeType.APPROVAL], known_targets=[]
    )


def test_child_before_parent_is_incomplete() -> None:
    """A link to a not-yet-known target (child before parent) is incomplete (§12 326)."""
    link = CausalLink(edge_type=EdgeType.INTENT, target_id="er-0", target_digest="d0")
    env = _env_with_links(link)
    assert not causal_chain_complete(
        env, required_parent_edge_types=[EdgeType.INTENT], known_targets=[]
    )


def test_unknown_edge_type_is_fail_closed() -> None:
    """An unregistered edge type is unconstructable (fail-closed, §2.5 A)."""
    with pytest.raises(ValueError):
        CausalLink(edge_type="NOT_A_REAL_EDGE", target_id="x", target_digest="d")


def test_timestamp_only_link_is_forbidden() -> None:
    """A causal link needs a concrete immutable target (no placeholder) (§2.5 A)."""
    with pytest.raises(ValueError):
        CausalLink(edge_type=EdgeType.INTENT, target_id="TBD", target_digest="d")


# ===========================================================================
# ERI-EV-009 — redaction preservation (predicate-only, §2.5 B / ERI-INV-010)
# ===========================================================================


def test_valid_redaction_preserves_all_safety_properties() -> None:
    """A valid profile preserves digest, field presence, and every safety property."""
    profile = RedactionProfile(
        profile_id="p1",
        removed_fields=("payload.secret",),
        preserves=tuple(PreservedProperty),
    )
    assert redaction_profile_valid(profile)
    assert redaction_preserves_digest(profile)


def test_profile_dropping_a_safety_property_is_invalid() -> None:
    """A profile that fails to preserve a safety property is INVALID (§22 528)."""
    profile = RedactionProfile(
        profile_id="p2",
        preserves=(PreservedProperty.SCOPE,),  # drops ORDERING/QUANTITIES/...
    )
    assert not redaction_profile_valid(profile)


def test_profile_not_preserving_digest_is_invalid() -> None:
    """A profile that does not preserve the canonical digest is INVALID (ERI-INV-010)."""
    profile = RedactionProfile(
        profile_id="p3",
        preserves=tuple(PreservedProperty),
        preserves_canonical_digest=False,
    )
    assert not redaction_profile_valid(profile)


# ===========================================================================
# ERI-EV-012 — repair non-revival (predicate-only, §4.7/§7)
# ===========================================================================


def test_repaired_gap_preserves_uncertainty() -> None:
    """A REPAIRED gap keeps residual uncertainty (repair != full strength, §14 372)."""
    gap = make_gap(GapStatus.REPAIRED)
    assert repair_preserves_uncertainty(gap)


def test_repaired_gap_claiming_resolved_uncertainty_violates() -> None:
    """A REPAIRED gap claiming RESOLVED uncertainty fails the non-revival predicate."""
    gap = make_gap(
        GapStatus.REPAIRED,
        repair=GapRepair(
            recovered_record_ids=("er-1",),
            recovery_sources=make_gap(GapStatus.REPAIRED).repair.recovery_sources,
            remaining_uncertainty=RemainingUncertainty.RESOLVED,
        ),
    )
    assert not repair_preserves_uncertainty(gap)


# ===========================================================================
# ERI-INV-001/014 — authority absence across all artifacts (always-on)
# ===========================================================================


def test_all_artifacts_grant_no_authority() -> None:
    """Every artifact's authority block grants nothing (ERI-INV-001/014, §4.6)."""
    assert grants_no_authority(issue_envelope().authority_effect)
    assert grants_no_authority(issue_eip().authority_effect)
    assert grants_no_authority(make_gap(GapStatus.SUSPECTED).authority_effect)
    assert grants_no_authority(issue_replay().result)


def test_true_envelope_authority_is_unconstructable() -> None:
    """A true envelope authority flag makes the envelope unconstructable (ERI-INV-014)."""
    from tos.evidence.envelope import EnvelopeAuthorityEffect

    with pytest.raises(ValueError):
        EnvelopeAuthorityEffect(may_transmit_to_broker=True)


# ===========================================================================
# §3.5 — EIP binding / policy substitution
# ===========================================================================


def test_eip_binding_ok_when_matching() -> None:
    """A matching EIP id + digest + generation binds (§3.5)."""
    eip = issue_eip(policy_id="eip-1", generation=1)
    env = issue_envelope(
        evidence_integrity_policy_id="eip-1",
        evidence_integrity_policy_generation=1,
        evidence_integrity_policy_digest=eip.canonical_digest,
    )
    assert eip_binding_ok(env, eip)


def test_eip_binding_rejects_digest_substitution() -> None:
    """A mismatched EIP digest is policy substitution / generation drift (§3.5)."""
    eip = issue_eip(policy_id="eip-1", generation=1)
    env = issue_envelope(
        evidence_integrity_policy_id="eip-1",
        evidence_integrity_policy_generation=1,
        evidence_integrity_policy_digest="wrong-digest",
    )
    assert not eip_binding_ok(env, eip)


def test_eip_binding_fails_closed_on_null_envelope_generation() -> None:
    """(MINOR-2) A null envelope generation cannot mask concrete-policy generation drift.

    ``generation`` is excluded from the EIP ``content_digest``, so an envelope that
    binds the right id + digest but leaves the generation null must NOT bind to a
    policy that carries a concrete generation (same-body generation drift).
    """
    eip = issue_eip(policy_id="eip-1", generation=2)
    env = issue_envelope(
        evidence_integrity_policy_id="eip-1",
        evidence_integrity_policy_generation=None,  # omitted
        evidence_integrity_policy_digest=eip.canonical_digest,
    )
    assert not eip_binding_ok(env, eip)


# ===========================================================================
# §2.2 — receipt binding + substitution rejection (predicate-only)
# ===========================================================================


def test_receipt_binds_matching_record() -> None:
    """A receipt binds to the record whose id + digest it carries (§2.2/§10.2 284)."""
    env = issue_envelope(evidence_record_id="er-1")
    receipt = issue_receipt(
        evidence_record_id="er-1", canonical_record_digest=env.canonical_digest
    )
    assert receipt_binds_record(receipt, env)


def test_receipt_does_not_bind_other_record() -> None:
    """A receipt does not bind a record with a different digest (§2.2)."""
    env = issue_envelope(evidence_record_id="er-1")
    receipt = issue_receipt(
        evidence_record_id="er-1", canonical_record_digest="some-other-digest"
    )
    assert not receipt_binds_record(receipt, env)


def test_receipt_substitution_rejected_on_request_mismatch() -> None:
    """A receipt for another request digest must be rejected (§10.2 286)."""
    receipt = issue_receipt(
        valid_for_request_digest="req-A", valid_for_scope_digest="sc"
    )
    assert receipt_substitution_rejected(
        receipt, expected_request_digest="req-B", expected_scope_digest="sc"
    )


def test_receipt_accepted_when_all_bindings_match() -> None:
    """A receipt matching request + scope + policy gen + continuity is not rejected."""
    receipt = issue_receipt(
        valid_for_request_digest="req-A",
        valid_for_scope_digest="sc",
        evidence_integrity_policy_generation=3,
        store_continuity_id="store-1",
    )
    assert not receipt_substitution_rejected(
        receipt,
        expected_request_digest="req-A",
        expected_scope_digest="sc",
        expected_policy_generation=3,
        expected_store_continuity_id="store-1",
    )


def test_receipt_rejected_on_stale_policy_generation() -> None:
    """A receipt bound to a stale EIP generation must be rejected (§22 522)."""
    receipt = issue_receipt(
        valid_for_request_digest="req-A",
        valid_for_scope_digest="sc",
        evidence_integrity_policy_generation=2,
    )
    assert receipt_substitution_rejected(
        receipt,
        expected_request_digest="req-A",
        expected_scope_digest="sc",
        expected_policy_generation=5,
    )


# ===========================================================================
# §2.0 — derived correction back-reference (forward scan)
# ===========================================================================


def test_corrected_by_derives_forward_correction() -> None:
    """A correcting record (supersedes + CORRECTION edge) is found by forward scan (§2.0)."""
    from tos.evidence.envelope import Causality, Lifecycle

    original = issue_envelope(evidence_record_id="er-1")
    corrector = issue_envelope(
        evidence_record_id="er-2",
        lifecycle=Lifecycle(retention_class="standard", supersedes_record_id="er-1"),
        causality=Causality(
            correlation_id="c",
            causal_links=(
                CausalLink(
                    edge_type=EdgeType.CORRECTION, target_id="er-1", target_digest="d"
                ),
            ),
        ),
    )
    assert corrected_by("er-1", [original, corrector]) == ("er-2",)
    # The original stores no back-reference (append-only; derived only).
    assert corrected_by("er-2", [original, corrector]) == ()


@given(seed=st.integers(0, 5))
def test_corrected_by_ignores_supersede_without_correction_edge(seed: int) -> None:
    """A plain supersession without a CORRECTION edge is not a correction (§2.0)."""
    from tos.evidence.envelope import Lifecycle

    original = issue_envelope(evidence_record_id="er-1")
    superseder = issue_envelope(
        evidence_record_id=f"er-{seed + 2}",
        lifecycle=Lifecycle(retention_class="standard", supersedes_record_id="er-1"),
    )
    assert corrected_by("er-1", [original, superseder]) == ()
