"""Test-only seam cross-check: replacement <-> evidence (design #18 §3.4 9th producer).

The v1.1 **C2** correction added a **ninth** producer row to §3.4: the §10 per-field
Protection Sufficiency Proof is produced by **evidence (ADR-002-006)** together with
brokercap ``broker_capability_sufficient``, and is a *different axis* from protective's
aggregate-risk classification. This file locks the replacement side of that seam plus the
§18 "Evidence Is Not Authority" rule.

**Honest disclosure (design #18 §3.4(b) — the #10 phantom lesson).** ``tos.evidence``
exposes **no** dedicated per-field Protection-Sufficiency predicate today; the §10 line
254-263 field-level proof is an ``EV-L3+Broker`` deferral (PR-EV-006 closes nothing). So
this seam does **not** cite a predicate that does not exist. What it locks instead is
real and checkable:

1. ``tos.replacement`` authors **no** per-field sufficiency producer — re-authoring one
   would duplicate the ADR-002-006 authority (design #18 §0.2/§6.3);
2. the §4.6a fail-closed gate on the ``new_protection_sufficiency_current`` slot — an
   emitted request, a transport ACK, or a stale proof can never reach it (§1 line 34,
   §10 line 267 "It does not remain sufficient by inertia");
3. the §18 line 410 rule that evidence grants no authority — asserted by driving the
   **evidence-owned** ``grants_no_authority`` over the replacement authority block;
4. that the replacement records use the **same** shared conflict classifier the evidence
   store uses, so a forged replacement authorization is a ``CRITICAL_CONFLICT`` under one
   single definition rather than two that could drift.

A test-only cross-import is **not** a runtime package edge (design #18 §3.4(d)/§7.1).
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.evidence import RecordPairKind as EvidenceRecordPairKind
from tos.evidence import classify_record_pair as evidence_classify_record_pair
from tos.evidence import grants_no_authority
from tos.replacement import (
    PROTECTION_SUFFICIENCY_FIELDS,
    ReplacementAuthorityEffect,
    ReplacementMode,
    overlap_first_sequencing_valid,
    workflow_label_grants_nothing,
)

from ._replacement_strategies import (
    FORGED_AUTHORITY_VALUES,
    TRUTHY_NON_BOOL,
    clean_sequencing_inputs,
    issue_authorization,
)

# ---------------------------------------------------------------------------
# 1. No re-authored per-field sufficiency producer (no duplication, no phantom)
# ---------------------------------------------------------------------------


def test_replacement_authors_no_per_field_sufficiency_producer() -> None:
    """(§0.2 / §6.3) The §10 field-level proof is evidence + brokercap owned.

    PR-EV-006 is minimum ``EV-L3+Broker``: replacement consumes a single injected
    ``new_protection_sufficiency_current`` bool and never derives it from fields itself.
    """
    from tos import replacement as replacement_pkg

    for forbidden in (
        "protection_sufficiency_proof",
        "new_protection_sufficiency",
        "field_proof_complete",
        "sufficiency_fields_established",
        "ProtectionSufficiencyProof",
    ):
        assert not hasattr(replacement_pkg, forbidden), (
            f"{forbidden} re-authors the ADR-002-006 / brokercap per-field proof — "
            "design #18 §6.3 defers it as an EV-L3+Broker coordinate"
        )


# ---------------------------------------------------------------------------
# 2. §4.6a — ACK / emission / inertia can never reach the sufficiency slot
# ---------------------------------------------------------------------------


@given(ack_like=st.sampled_from(TRUTHY_NON_BOOL))
def test_ack_or_emission_evidence_never_becomes_effective_protection(
    ack_like: object,
) -> None:
    """(§1 line 34 / §4.6a) "a request emitted or transport ACK ... does not count".

    A producer that drops an ACK payload, a transport status token, or a truthy sentinel
    into the sufficiency slot must not be able to cancel the old protective order.
    """
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(new_protection_sufficiency_current=ack_like)
        )
        is False
    )


def test_a_stale_or_contradicted_proof_does_not_remain_sufficient_by_inertia() -> None:
    """(§10 line 267, both ways) Staleness is modelled as the slot going non-``True``.

    "If the proof becomes stale, contradicted, or insufficient, the protection state
    becomes ``UNKNOWN`` or gap-exposed ... It does not remain sufficient by inertia."
    """
    # (a) guard fires — the proof went stale (``None``) or was contradicted (``False``).
    for stale in (None, False):
        assert (
            overlap_first_sequencing_valid(
                **clean_sequencing_inputs(new_protection_sufficiency_current=stale)
            )
            is False
        )
    # (b) passing side — a current, positively established proof does not block.
    assert overlap_first_sequencing_valid(**clean_sequencing_inputs()) is True


# ---------------------------------------------------------------------------
# 3. §18 line 410 — Evidence Is Not Authority (evidence-owned predicate, driven here)
# ---------------------------------------------------------------------------


def test_the_evidence_owned_authority_check_agrees_with_the_replacement_one() -> None:
    """(§18 / §5 line 137) The replacement authority block grants nothing, both ways.

    The evidence store owns ``grants_no_authority``; driving it over the replacement
    block proves the two packages agree that a replacement record is evidence, not
    permission.
    """
    effect = ReplacementAuthorityEffect()
    assert grants_no_authority(effect) is True
    assert workflow_label_grants_nothing(effect) is True


@given(forged=st.sampled_from(FORGED_AUTHORITY_VALUES))
def test_a_forged_authority_flag_is_caught_by_the_replacement_recheck(
    forged: object,
) -> None:
    """(defence in depth) The replacement re-check is strictly the stronger of the two.

    ``grants_no_authority`` tests ``is True``, so a forged truthy non-``bool`` (``1`` /
    ``"yes"`` / ``[1]``) slips past it; the replacement re-check tests ``is False`` and
    catches every one. Both agree on the singleton ``True``.
    """
    forged_block = ReplacementAuthorityEffect.model_construct(releases_capacity=forged)
    assert workflow_label_grants_nothing(forged_block) is False
    if forged is True:
        assert grants_no_authority(forged_block) is False


def test_an_issued_authorization_carries_an_all_false_authority_block() -> None:
    """(§5 line 137) Even a fully-issued, digest-bound authorization grants nothing."""
    authorization = issue_authorization(replacement_mode=ReplacementMode.CANCEL_FIRST)
    assert grants_no_authority(authorization.authority_effect) is True
    assert workflow_label_grants_nothing(authorization.authority_effect) is True


# ---------------------------------------------------------------------------
# 4. One shared conflict classifier (§5.4) — no second, drifting definition
# ---------------------------------------------------------------------------


def test_the_replacement_records_use_the_same_conflict_vocabulary_as_evidence() -> None:
    """(§3.1 / §5.4) The record-pair classification is core-promoted and single-sourced.

    ``tos.evidence`` layers an envelope-shaped wrapper over the promoted core
    ``classify_record_pair`` (which takes bare identity / digest coordinates), but both
    resolve to the **same** ``RecordPairKind`` enum. A forged replacement authorization is
    therefore a ``CRITICAL_CONFLICT`` under **one** definition, not two that could drift.
    """
    from tos.canonical import RecordPairKind as CanonicalRecordPairKind
    from tos.canonical import classify_record_pair as canonical_classify

    assert EvidenceRecordPairKind is CanonicalRecordPairKind
    # The evidence-facing entry point is a wrapper over the same core rule, not a rival
    # implementation: it consumes envelopes where the core consumes coordinates.
    assert evidence_classify_record_pair is not canonical_classify
    assert evidence_classify_record_pair.__module__.startswith(
        "tos.evidence"
    ), "the evidence wrapper must stay in evidence; the rule itself stays in core"

    a = issue_authorization(replacement_mode=ReplacementMode.OVERLAP_FIRST)
    b = issue_authorization(replacement_mode=ReplacementMode.CANCEL_FIRST)
    assert (
        canonical_classify(
            a.authorization_id,
            a.canonical_digest,
            b.authorization_id,
            b.canonical_digest,
        )
        is EvidenceRecordPairKind.CRITICAL_CONFLICT
    )


# ---------------------------------------------------------------------------
# 5. §4.6a — the §1 line 34 eight-field universe (transcription count cross-check)
# ---------------------------------------------------------------------------


def test_the_eight_sufficiency_fields_are_transcribed_and_counted() -> None:
    """(§4.6a, count = **8**) ADR §1 line 34 names eight axes, verbatim and complete.

    "Its identity, quantity, side, price or trigger semantics, remaining quantity, venue
    state, broker capability, and relation to current exposure SHALL be positively
    established within approved freshness and confidence bounds."

    The count cross-check is the #16 M4 lesson applied to §1 line 34: a *dropped* axis
    would silently narrow what the producer owes.
    """
    assert len(PROTECTION_SUFFICIENCY_FIELDS) == 8
    assert len(set(PROTECTION_SUFFICIENCY_FIELDS)) == 8
    assert PROTECTION_SUFFICIENCY_FIELDS == (
        "identity",
        "quantity",
        "side",
        "price_or_trigger_semantics",
        "remaining_quantity",
        "venue_state",
        "broker_capability",
        "relation_to_current_exposure",
    )


def test_the_eight_fields_are_a_transcription_not_a_producer() -> None:
    """(§4.6a / §6.3) No model or predicate assembles sufficiency from these names.

    If the tuple were wired into a model or a derivation, ``tos.replacement`` would have
    re-authored the ADR-002-006 per-field proof. It is documentation-grade only: the
    package's single sufficiency input stays the injected bool.
    """
    from tos.replacement import CancelFirstConditions, records

    for field in PROTECTION_SUFFICIENCY_FIELDS:
        for model in (
            CancelFirstConditions,
            records.OverlapReservationClaim,
            records.ReplacementAuthorization,
            records.ReplacementWorkflowRecord,
        ):
            assert field not in model.model_fields, (
                f"{field} became a replacement model field — the §10 per-field proof is "
                "evidence / brokercap owned (design #18 §6.3)"
            )
