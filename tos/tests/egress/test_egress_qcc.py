"""Core §5.1-§5.4 — Quorum Commit Certificate structural validation (design #22; EGRESS-EV-004).

Covers the four QCC yolk predicates: structural completeness (§5.1), coordinate currency (§5.2),
quorum threshold shape with dedup interpretation B + lone-leader rejection (§5.3), and the
evidence-receipt-is-not-a-QCC rejection (§5.4). The over-realization boundary is asserted: the
threshold predicate is a distinct-count over **injected** verified-flags, never a signature check.

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV-004 substrate;
EV-L1-complete claim forbidden. Over-realization boundary: cryptographic / consensus validity is
+Security; L1 is structure / coordinate / count only.
"""

from __future__ import annotations

from hypothesis import given
from tos.egress import (
    QuorumCommitCertificate,
    SignerRole,
    evidence_receipt_is_not_quorum_proof,
    quorum_commit_certificate_structurally_complete,
    quorum_coordinates_current,
    quorum_threshold_structurally_met,
)

from ._egress_strategies import (
    clean_current_coordinates,
    clean_qcc,
    clean_signer,
    clean_signers,
    expected_quorum_threshold,
    signer_sets,
)

# ---- §5.1 structural completeness ----------------------------------------


def test_clean_qcc_is_structurally_complete() -> None:
    """(§5.1) A clean, fully-populated QCC with two signers + both nonces is complete."""
    assert quorum_commit_certificate_structurally_complete(clean_qcc()) is True


def test_none_qcc_is_incomplete() -> None:
    """(§5.1 fail-closed) A None QCC is not structurally complete."""
    assert quorum_commit_certificate_structurally_complete(None) is False


def test_qcc_with_empty_signers_is_incomplete() -> None:
    """(§5.1 (iii) / §4.7) An ∅ signer set fails structural completeness."""
    qcc = clean_qcc(signer_coordinates=())
    assert quorum_commit_certificate_structurally_complete(qcc) is False


def test_qcc_missing_a_nonce_is_incomplete() -> None:
    """(§5.1 (ii)) A None capability / permit nonce fails structural completeness."""
    assert (
        quorum_commit_certificate_structurally_complete(
            clean_qcc(capability_nonce=None)
        )
        is False
    )
    assert (
        quorum_commit_certificate_structurally_complete(
            clean_qcc(action_flow_permit_nonce=None)
        )
        is False
    )


def test_model_construct_bypass_incomplete_qcc_still_rejected() -> None:
    """(§2.3 defence-in-depth) A model_construct-bypassed None-required QCC fails the §5.1 predicate."""
    # model_construct skips validators, so a required-None QCC can be built — the predicate re-checks.
    bypassed = QuorumCommitCertificate.model_construct(
        qcc_id="qcc-x",
        cluster_identity=None,  # required-covered left None
        signer_coordinates=clean_signers(),
        capability_nonce="n1",
        action_flow_permit_nonce="n2",
    )
    assert quorum_commit_certificate_structurally_complete(bypassed) is False


def test_model_construct_bypass_malformed_trial_still_rejected() -> None:
    """(§2.3 defence-in-depth) A model_construct-bypassed malformed trial-claim QCC fails §5.1."""
    from tos.egress import TrialClaims

    base = clean_qcc()
    bypassed = base.model_copy(
        update={
            "is_restricted_live_trial": True,
            "trial_claims": TrialClaims(trial_policy_generation=1),  # incomplete
        }
    )
    # model_copy also skips the after-validator re-run for the coexistence rule in some paths;
    # the §5.1 predicate re-checks the trial completeness regardless.
    assert quorum_commit_certificate_structurally_complete(bypassed) is False


# ---- §5.2 coordinate currency --------------------------------------------


def test_current_coordinates_match_passes() -> None:
    """(§5.2) A QCC whose coordinates equal the injected current committed values passes."""
    assert quorum_coordinates_current(clean_qcc(), clean_current_coordinates()) is True


def test_stale_coordinate_fails() -> None:
    """(§5.2) Any stale / mismatched carried coordinate fails currency."""
    qcc = clean_qcc()
    assert (
        quorum_coordinates_current(
            qcc, clean_current_coordinates(committed_revision=999)
        )
        is False
    )


def test_none_current_or_qcc_fails_currency() -> None:
    """(§5.2 fail-closed) A None QCC / None current coordinates fail currency."""
    assert quorum_coordinates_current(None, clean_current_coordinates()) is False
    assert quorum_coordinates_current(clean_qcc(), None) is False


def test_none_carried_coordinate_fails_currency() -> None:
    """(§5.2 fail-closed) A None carried coordinate (vs a concrete current) fails currency."""
    # Build a QCC missing a NON-required coordinate (route_policy_generation) via model_copy bypass.
    qcc = clean_qcc().model_copy(update={"route_policy_generation": None})
    assert quorum_coordinates_current(qcc, clean_current_coordinates()) is False


# ---- §5.3 quorum threshold shape (dedup interpretation B) -----------------


def test_two_distinct_eligible_signed_meets_quorum_two() -> None:
    """(§5.3) Two distinct eligible-and-signed members meet quorum N=2."""
    assert quorum_threshold_structurally_met(clean_signers(), 2) is True


def test_quorum_n_zero_is_vacuous_denial() -> None:
    """(§5.3 (i) / §4.7) A degenerate quorum_n of 0 is denial (not vacuously satisfied)."""
    assert quorum_threshold_structurally_met(clean_signers(), 0) is False


def test_quorum_n_none_is_denial() -> None:
    """(§5.3 (i)) A None quorum_n is denial."""
    assert quorum_threshold_structurally_met(clean_signers(), None) is False


def test_empty_signer_set_is_denial() -> None:
    """(§5.3 (v) / §4.7) An ∅ signer set is denial (0 < N)."""
    assert quorum_threshold_structurally_met((), 1) is False


def test_lone_leader_is_insufficient() -> None:
    """(§5.3 (iv) / §11.2:351) A lone LEADER signature does not meet quorum N=1."""
    lone = (clean_signer(signer_identity="L", signer_role=SignerRole.LEADER),)
    assert quorum_threshold_structurally_met(lone, 1) is False


def test_lone_quorum_member_meets_quorum_one() -> None:
    """(§5.3 both-ways) A single non-leader quorum member DOES meet a policy quorum of N=1."""
    lone = (clean_signer(signer_identity="M", signer_role=SignerRole.QUORUM_MEMBER),)
    assert quorum_threshold_structurally_met(lone, 1) is True


def test_dedup_b_conflicting_entry_excludes_identity() -> None:
    """(§5.3 dedup-B) A conflicting (unverified) entry for an identity EXCLUDES that identity."""
    good_a = clean_signer(signer_identity="a")
    good_b = clean_signer(signer_identity="b")
    # A second 'a' entry with eligible_verified=None conflicts ⇒ 'a' is excluded (only 'b' counts).
    conflicting_a = clean_signer(signer_identity="a", eligible_verified=None)
    signers = (good_a, conflicting_a, good_b)
    # dedup-B: only 'b' counts ⇒ 1 < 2 ⇒ denial (the forged-entry-piggyback fail-open is blocked).
    assert quorum_threshold_structurally_met(signers, 2) is False
    # With N=1 the surviving 'b' still meets the threshold (availability side of dedup-B).
    assert quorum_threshold_structurally_met(signers, 1) is True


def test_dedup_duplicate_agreeing_entries_count_once() -> None:
    """(§5.3 dedup) Duplicate agreeing entries for one identity count that identity once."""
    a1 = clean_signer(signer_identity="a")
    a2 = clean_signer(signer_identity="a")  # same identity, both eligible + signed
    b = clean_signer(signer_identity="b")
    # 'a' counted once + 'b' = 2 distinct ⇒ meets N=2.
    assert quorum_threshold_structurally_met((a1, a2, b), 2) is True
    # …but not N=3 (only two distinct identities).
    assert quorum_threshold_structurally_met((a1, a2, b), 3) is False


def test_unverified_or_none_flag_signer_not_counted() -> None:
    """(§5.3 over-realization) A signer with a None / False injected flag is not counted."""
    unsigned = clean_signer(signer_identity="x", signature_verified=False)
    ineligible = clean_signer(signer_identity="y", eligible_verified=None)
    assert quorum_threshold_structurally_met((unsigned, ineligible), 1) is False


# ---- §5.3 MAJOR-1 — lone-signer carve-out is role-safe (order-independent) ------------------


def test_lone_none_role_signer_is_insufficient() -> None:
    """(§5.3 MAJOR-1) A lone verified signer with a None role is NOT a confirmed quorum member ⇒ False.

    A ``None`` role is not positive proof of QUORUM_MEMBER; ADR §11.2:351 "One leader signature ...
    is insufficient" is realized by requiring a positively-confirmed member for a lone signer.
    """
    none_role = clean_signer(signer_identity="n", signer_role=None)
    assert quorum_threshold_structurally_met((none_role,), 1) is False


def test_lone_signer_role_reconcile_is_order_independent() -> None:
    """(§5.3 MAJOR-1) A duplicate-entry role conflict is rejected regardless of input order.

    The same identity carrying both a QUORUM_MEMBER entry and a LEADER entry must NOT let a genuine
    leader signature slip through by role-label duplication — the verdict must be identical whether
    the member entry or the leader entry appears first (no ``entries[0]`` order dependence).
    """
    member = clean_signer(signer_identity="a", signer_role=SignerRole.QUORUM_MEMBER)
    leader = clean_signer(signer_identity="a", signer_role=SignerRole.LEADER)
    member_first = quorum_threshold_structurally_met((member, leader), 1)
    leader_first = quorum_threshold_structurally_met((leader, member), 1)
    assert member_first is False
    assert leader_first is False
    assert member_first == leader_first


def test_lone_confirmed_quorum_member_is_sufficient_for_n1() -> None:
    """(§5.3 MAJOR-1 positive side) A lone, all-entries-agree QUORUM_MEMBER meets a policy N=1."""
    member = clean_signer(signer_identity="a", signer_role=SignerRole.QUORUM_MEMBER)
    assert quorum_threshold_structurally_met((member,), 1) is True
    # Duplicate agreeing member entries (both QUORUM_MEMBER) still confirm the lone identity.
    dup = clean_signer(signer_identity="a", signer_role=SignerRole.QUORUM_MEMBER)
    assert quorum_threshold_structurally_met((member, dup), 1) is True


@given(signer_sets())
def test_threshold_matches_oracle_bidirectionally(data) -> None:
    """(§5.3 property) The predicate is exactly equivalent to the full spec oracle (both directions)."""
    signers, quorum_n = data
    result = quorum_threshold_structurally_met(signers, quorum_n)
    expected = expected_quorum_threshold(signers, quorum_n)
    assert result == expected


# ---- §5.4 evidence receipt is not a quorum proof -------------------------


def test_evidence_receipt_is_never_a_quorum_proof() -> None:
    """(§5.4) An evidence receipt / leader receipt / journal can never substitute for a QCC."""
    assert evidence_receipt_is_not_quorum_proof(None) is True
    assert evidence_receipt_is_not_quorum_proof(object()) is True
    assert evidence_receipt_is_not_quorum_proof("a-leader-receipt") is True
