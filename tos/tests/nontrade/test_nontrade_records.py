"""§2.1/§2.3/§5.6 record model: digest binding, identity axes, all-false authority.

The two digest-bound citizens are ``IndependentIdArtifact``s precisely so **two** forgery
axes stay detectable (design #21 §0.4f): a same **primary** id / different-bytes pair and a
same **idempotency key** / different-bytes pair. The ``_ID_FIELD`` / ``_REQUIRED_COVERED``
/ ``_COVERED_FIELDS`` class variables are **drift-locked** here (design #21 §9.1(4b)):
silently moving a field out of the covered set would leave it unbound by the digest — a
change that no behavioural test would notice.

This module also pins the **absence** of the three phantom negative-polarity fields that
design #21 M7 deleted, and the absence of any transmit / mutate / release method (§4.4).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.canonical import ArtifactStatus, RecordPairKind, classify_record_pair
from tos.nontrade import (
    ORTHOGONAL_EVENT_AXES,
    AllFalseNonTradeAuthority,
    ArtifactIntegrityError,
    CorrectionReversalRecord,
    CredibleTransitionLegKind,
    NonTradeAuthorityEffect,
    NonTradeEventRecord,
    NonTradeEventWorkflowState,
    SplitTransformationSpec,
    TransitionEnvelope,
    nontrade_authority_effect_all_false,
)

from ._nontrade_strategies import (
    FORGED_AUTHORITY_VALUES,
    PHANTOM_NEGATIVE_POLARITY_FIELDS,
    clean_envelope,
    clean_spec,
    issue_correction,
    issue_event,
)

# ---------------------------------------------------------------------------
# Digest binding + required-covered completeness
# ---------------------------------------------------------------------------


def test_a_clean_event_and_correction_issue_and_verify() -> None:
    """(availability side) The clean fixtures are genuinely ISSUED, not shortcuts."""
    event = issue_event()
    correction = issue_correction()
    assert event.status is ArtifactStatus.ISSUED
    assert correction.status is ArtifactStatus.ISSUED
    assert event.canonical_digest is not None
    assert correction.canonical_digest is not None
    assert event.missing_required_fields() == []
    assert correction.missing_required_fields() == []


def test_issuing_is_deterministic_for_identical_covered_content() -> None:
    """(§7.2 determinism) Two identical issuances share one digest.

    This also proves the ``present_legs`` normalization: the leg tuple is sorted at
    validation time, so a set-shaped input can never make the digest hash-seed dependent.
    """
    first = issue_event()
    second = issue_event()
    assert first.canonical_digest == second.canonical_digest
    shuffled = issue_event(
        transition_envelope=clean_envelope(
            present_legs=tuple(reversed(list(CredibleTransitionLegKind)))
        )
    )
    assert shuffled.canonical_digest == first.canonical_digest


def test_a_substituted_covered_field_changes_the_digest() -> None:
    """(§4.1) Every covered field is genuinely bound by the digest."""
    base = issue_event()
    for field, value in (
        ("event_subtype", "reverse-split"),
        ("effective_time", "t-effective-2"),
        ("old_instrument_identity", "canonical-instrument-old-2"),
        ("idempotency_key", "nt-idem-2"),
        ("workflow_state", NonTradeEventWorkflowState.VALIDATED),
        ("capacity_state", "TRAPPED_CONSUMED"),
    ):
        mutated = issue_event(**{field: value})
        assert (
            mutated.canonical_digest != base.canonical_digest
        ), f"{field} is not bound by the digest"


def test_a_forged_digest_is_unconstructable() -> None:
    """(§4.1) A stored digest that does not match the covered content is rejected."""
    event = issue_event()
    with pytest.raises(ValueError, match="canonical_digest"):
        NonTradeEventRecord(
            **{
                **event.model_dump(),
                "canonical_digest": "0" * 64,
            }
        )


def test_an_issued_record_requires_a_concrete_independent_id() -> None:
    """(canonical §3.1) ``id != f(digest)`` but an ISSUED id must still be concrete."""
    with pytest.raises(ValueError, match="event_id"):
        issue_event(event_id=None)
    with pytest.raises(ValueError, match="correction_id"):
        issue_correction(correction_id=None)


def test_a_missing_required_covered_field_blocks_issuance() -> None:
    """(§3.2) The structural identity / classification fields must be concrete."""
    for field in NonTradeEventRecord._REQUIRED_COVERED:
        with pytest.raises(ValueError, match="required safety-load-bearing"):
            issue_event(**{field: None})
    for field in CorrectionReversalRecord._REQUIRED_COVERED:
        with pytest.raises(ValueError, match="required safety-load-bearing"):
            issue_correction(**{field: None})


def test_a_lineage_less_correction_stays_constructible() -> None:
    """(§16 line 311 reachability) ``supersedes_ref`` is deliberately NOT required-covered.

    If it were, a lineage-less correction would be unconstructable and the
    ``REJECTED_NO_LINEAGE`` guard would be vacuous — the rule would silently leave the
    decision layer.
    """
    record = issue_correction(supersedes_ref=None)
    assert record.status is ArtifactStatus.ISSUED
    assert record.supersedes_ref is None
    assert "supersedes_ref" not in CorrectionReversalRecord._REQUIRED_COVERED


# ---------------------------------------------------------------------------
# ``_ID_FIELD`` / covered-set drift locks (§9.1(4b))
# ---------------------------------------------------------------------------


def test_id_field_drift_lock() -> None:
    """(§9.1(4b)) The independent id field names are pinned.

    ``classify_record_pair`` is called with these exact attributes, so renaming one without
    updating the predicate would silently pass ``None`` as the primary identity — and
    ``a_identity is None`` short-circuits the ``same_identity`` branch, downgrading a
    forged record from ``CRITICAL_CONFLICT`` to ``DISTINCT``.
    """
    assert NonTradeEventRecord._ID_FIELD == "event_id"
    assert CorrectionReversalRecord._ID_FIELD == "correction_id"


def test_the_id_field_is_self_excluded_from_the_digest_preimage() -> None:
    """(§2.3/§3.1) The independent id is Layer-0: never part of the covered content."""
    assert NonTradeEventRecord._ID_FIELD not in NonTradeEventRecord._COVERED_FIELDS
    assert (
        CorrectionReversalRecord._ID_FIELD
        not in CorrectionReversalRecord._COVERED_FIELDS
    )
    for excluded in ("canonical_digest", "status", "canonicalization_version"):
        assert excluded not in NonTradeEventRecord._COVERED_FIELDS
        assert excluded not in CorrectionReversalRecord._COVERED_FIELDS


def test_ledger_placement_and_authority_are_self_excluded() -> None:
    """(§2.3) Placement order and the all-false authority stay out of the preimage.

    The authority block is all-false by construction, so covering it would add nothing to
    the digest while making a future flag addition a digest-breaking change.
    """
    assert "event_order" not in NonTradeEventRecord._COVERED_FIELDS
    assert "authority_effect" not in NonTradeEventRecord._COVERED_FIELDS
    assert "correction_order" not in CorrectionReversalRecord._COVERED_FIELDS
    assert "authority_effect" not in CorrectionReversalRecord._COVERED_FIELDS


def test_every_covered_field_actually_exists_on_its_model() -> None:
    """(drift lock) A covered name that is not a field would silently bind nothing."""
    for model in (NonTradeEventRecord, CorrectionReversalRecord):
        fields = set(model.model_fields)
        missing = sorted(model._COVERED_FIELDS - fields)
        assert missing == [], f"{model.__name__} covers non-existent fields: {missing}"
        required_missing = sorted(set(model._REQUIRED_COVERED) - fields)
        assert required_missing == []
        # every required-covered path must itself be covered by the digest
        assert set(model._REQUIRED_COVERED) <= model._COVERED_FIELDS


def test_the_five_orthogonal_axes_are_covered_and_separate() -> None:
    """(§6 line 123) The five axes are separate covered fields, distinct from workflow_state."""
    for axis in ORTHOGONAL_EVENT_AXES:
        assert axis in NonTradeEventRecord.model_fields
        assert axis in NonTradeEventRecord._COVERED_FIELDS
    assert "workflow_state" in NonTradeEventRecord._COVERED_FIELDS
    assert "workflow_state" not in ORTHOGONAL_EVENT_AXES


# ---------------------------------------------------------------------------
# The two forgery axes (§4.6)
# ---------------------------------------------------------------------------


def test_same_primary_id_different_bytes_is_a_critical_conflict() -> None:
    """(§4.6 forgery axis 1) A forged / contradictory event keeps its id and changes bytes."""
    original = issue_event()
    forged = issue_event(event_subtype="reverse-split")
    assert original.event_id == forged.event_id
    assert original.canonical_digest != forged.canonical_digest
    assert (
        classify_record_pair(
            original.event_id,
            original.canonical_digest,
            forged.event_id,
            forged.canonical_digest,
            a_idempotency_id=original.idempotency_key,
            b_idempotency_id=forged.idempotency_key,
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_same_idempotency_key_different_bytes_is_a_divergent_emission() -> None:
    """(§4.6 forgery axis 2) Two **different** records claiming one idempotency key."""
    first = issue_correction(correction_id="nt-corr-a")
    second = issue_correction(correction_id="nt-corr-b", correction_kind="REVERSAL")
    assert first.correction_id != second.correction_id
    assert first.idempotency_key == second.idempotency_key
    assert first.canonical_digest != second.canonical_digest
    assert (
        classify_record_pair(
            first.correction_id,
            first.canonical_digest,
            second.correction_id,
            second.canonical_digest,
            a_idempotency_id=first.idempotency_key,
            b_idempotency_id=second.idempotency_key,
        )
        is RecordPairKind.DIVERGENT_EMISSION
    )


def test_id_is_not_derived_from_the_digest() -> None:
    """(§0.4f) ``id != f(digest)`` — otherwise both forgery detections would be vacuous."""
    event = issue_event()
    assert event.canonical_digest is not None
    assert event.event_id not in (
        event.canonical_digest,
        f"nt-{event.canonical_digest}",
    )
    # a different id over identical covered content keeps the SAME digest, which is what
    # makes "same digest, different id" and "same id, different digest" both expressible
    relabelled = issue_event(event_id="nt-event-2")
    assert relabelled.canonical_digest == event.canonical_digest


# ---------------------------------------------------------------------------
# All-false authority (§6 line 144)
# ---------------------------------------------------------------------------


def test_the_authority_effect_declares_the_four_verbatim_flags_and_the_four_seals() -> (
    None
):
    """(§6 line 144 / §10 / §15 / §1) Eight flags, all false by default."""
    effect = NonTradeAuthorityEffect()
    for flag in (
        "releases_capacity",
        "closes_instrument",
        "proves_final_quantity",
        "grants_authority",
        "mutates_capacity",
        "issues_admissibility",
        "permits_transmission",
        "fabricates_fill",
    ):
        assert flag in NonTradeAuthorityEffect.model_fields
        assert getattr(effect, flag) is False
    assert nontrade_authority_effect_all_false(effect) is True


@pytest.mark.parametrize("flag", sorted(NonTradeAuthorityEffect.model_fields))
def test_any_true_authority_flag_is_unconstructable(flag: str) -> None:
    """(§6 line 144) A label grants nothing — a ``True`` flag cannot be built.

    pydantic wraps the :class:`~tos.nontrade.ArtifactIntegrityError` raised by the
    ``after`` validator in a ``ValidationError`` (itself a ``ValueError``), so the assertion
    matches on the message the integrity error carries.
    """
    assert issubclass(ArtifactIntegrityError, ValueError)
    with pytest.raises(ValueError, match=f"{flag} must be false"):
        NonTradeAuthorityEffect(**{flag: True})


@given(st.sampled_from(list(NonTradeEventWorkflowState)))
def test_every_workflow_state_carries_an_all_false_authority(
    state: NonTradeEventWorkflowState,
) -> None:
    """(§6 line 142/143/144) ``APPLIED_LOCAL`` and ``RECONCILED`` grant nothing either."""
    event = issue_event(workflow_state=state)
    assert nontrade_authority_effect_all_false(event.authority_effect) is True


@pytest.mark.parametrize("forged", FORGED_AUTHORITY_VALUES)
def test_a_forged_authority_flag_is_caught_by_the_defence_in_depth_recheck(
    forged: object,
) -> None:
    """(§5.4) ``model_construct`` skips validators — the re-check demands singleton ``False``.

    Each forged value is truthy but is not ``False``, so an ``is not True`` re-check would
    have cleared the non-``bool`` ones. The predicate demands ``is False``.
    """
    effect = NonTradeAuthorityEffect.model_construct(releases_capacity=forged)
    assert nontrade_authority_effect_all_false(effect) is False


def test_a_none_authority_block_proves_nothing() -> None:
    """(∅ guard) No block to check is not "nothing to prove"."""
    assert nontrade_authority_effect_all_false(None) is False


def test_a_zero_field_authority_block_proves_nothing_either() -> None:
    """(∅ guard, the base class itself) A block that declares **no** flag proves nothing.

    :class:`~tos.nontrade.AllFalseNonTradeAuthority` is the bare base: it declares zero
    boolean flags, so ``all(...)`` over its (empty) field set is vacuously ``True``. That
    is the ∅-vacuous shape the series rejects — "there is nothing to check" is not "the
    check passed" — so the predicate's explicit empty-field guard returns ``False``.

    Without this canary, deleting that guard would leave every test green while handing a
    caller a way to satisfy the label-grants-nothing conjunct with a flagless stand-in.
    """
    assert nontrade_authority_effect_all_false(AllFalseNonTradeAuthority()) is False
    # ...and the real subclass, which *does* declare flags, still passes (availability).
    assert len(NonTradeAuthorityEffect.model_fields) > 0
    assert nontrade_authority_effect_all_false(NonTradeAuthorityEffect()) is True


def test_no_record_or_value_model_has_a_transmit_or_mutate_method() -> None:
    """(§4.4/§0.2) No transmit / release / remap / issue path exists on any model."""
    for model in (
        NonTradeEventRecord,
        CorrectionReversalRecord,
        TransitionEnvelope,
        SplitTransformationSpec,
        NonTradeAuthorityEffect,
    ):
        for forbidden in (
            "transmit",
            "send",
            "release",
            "release_capacity",
            "commit",
            "remap",
            "mutate",
            "update",
            "issue_admissibility",
            "set_state",
            "close_instrument",
        ):
            assert not hasattr(
                model, forbidden
            ), f"{model.__name__}.{forbidden} exists — §4.4 forbids any enforcement path"


# ---------------------------------------------------------------------------
# Phantom negative-polarity fields (§0.1(8) / M7 honest disclosure)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phantom", PHANTOM_NEGATIVE_POLARITY_FIELDS)
def test_the_deleted_negative_polarity_fields_stay_absent(phantom: str) -> None:
    """(M7) ``favorable_netted`` / ``destructive_overwrite`` / ``released_on_transformation``.

    Phase-1 nontrade has **zero** negative-polarity fields: no-netting is a structural
    magnitude derivation, history preservation is the positive ``original_retained``, and a
    capacity release is unrepresentable. Reintroducing any of these names would hand a
    caller a forgeable flag on exactly the axes the design closed.
    """
    for model in (
        NonTradeEventRecord,
        CorrectionReversalRecord,
        TransitionEnvelope,
        SplitTransformationSpec,
        NonTradeAuthorityEffect,
    ):
        assert (
            phantom not in model.model_fields
        ), f"{model.__name__}.{phantom} reintroduces a forgeable negative-polarity flag"


def test_no_model_declares_any_direction_field() -> None:
    """(M2) The split polarity is derived — there is no direction field to mis-declare."""
    for name in ("quantity_direction", "basis_direction", "direction"):
        assert name not in SplitTransformationSpec.model_fields


# ---------------------------------------------------------------------------
# Value-model behaviour
# ---------------------------------------------------------------------------


def test_the_envelope_leg_tuple_is_deduplicated_and_sorted() -> None:
    """(digest determinism) A leg set has no intrinsic order; the record must."""
    legs = (
        CredibleTransitionLegKind.SOURCE_DISAGREEMENT_AND_TIME_UNCERTAINTY,
        CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER,
        CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER,
    )
    envelope = TransitionEnvelope(present_legs=legs)
    assert list(envelope.present_legs) == sorted(set(legs), key=lambda leg: leg.value)
    assert len(envelope.present_legs) == 2
    assert envelope.present_leg_set() == {
        CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER,
        CredibleTransitionLegKind.SOURCE_DISAGREEMENT_AND_TIME_UNCERTAINTY,
    }


def test_an_unsupplied_leg_magnitude_is_none_not_zero() -> None:
    """(§0.4d) ``None`` is UNKNOWN, never "no risk"."""
    envelope = TransitionEnvelope()
    assert (
        envelope.magnitude_of(CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER)
        is None
    )
    populated = clean_envelope()
    assert populated.magnitude_of(
        CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER
    ) == Decimal("1")


def test_the_models_are_frozen_and_forbid_extra_fields() -> None:
    """(§2) Immutable and schema-strict: no unknown field can smuggle a change."""
    envelope = clean_envelope()
    with pytest.raises(ValueError, match="frozen|immutable"):
        envelope.pre_event_exposure = Decimal("1")  # type: ignore[misc]
    with pytest.raises(ValueError, match="[Ee]xtra"):
        TransitionEnvelope(unexpected_field="x")
    with pytest.raises(ValueError, match="[Ee]xtra"):
        clean_spec(favorable_netted=False)


def test_canonical_decimal_normalizes_scale_at_the_record_level() -> None:
    """(§3.1) ``1.0`` and ``1.00`` are one artifact — a digest must not split on scale."""
    first = clean_envelope(pre_event_exposure=Decimal("7.0"))
    second = clean_envelope(pre_event_exposure=Decimal("7.00"))
    assert first.pre_event_exposure == second.pre_event_exposure
    assert (
        issue_event(transition_envelope=first).canonical_digest
        == issue_event(transition_envelope=second).canonical_digest
    )
