"""§5.4 evidence-substrate properties — digest binding, forgery, label-grants-nothing.

ADR §18 line 393-410 requires each replacement decision to be reconstructable from durable
evidence; the Phase-1 realization is the pair of frozen, digest-bound, generation-immutable
records (design #18 §5.4). The **replay engine itself is ADR-002-016 runtime** and the §18
line 408 nine required metrics are runtime observation, so neither is asserted here.

The forgery properties are the ``id != f(digest)`` payoff (design #18 §0.4e): because the
id is *independent*, a same-id / different-bytes pair stays representable, and
``classify_record_pair`` classifies it ``CRITICAL_CONFLICT`` — both sides preserved, no
last-write-wins. A content-addressed (``id = f(digest)``) record could not even express
the conflict.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from tos.canonical import ArtifactStatus, RecordPairKind, classify_record_pair
from tos.replacement import (
    ArtifactIntegrityError,
    ProtectionObligation,
    ReplacementAuthorityEffect,
    ReplacementAuthorization,
    ReplacementMode,
    ReplacementWorkflowRecord,
    ReplacementWorkflowState,
    workflow_generation_append_only,
    workflow_generation_order,
    workflow_label_grants_nothing,
    workflow_record_axes_not_collapsed,
)

from ._replacement_strategies import (
    FORGED_AUTHORITY_VALUES,
    WORKFLOW_STATES,
    issue_authorization,
    issue_workflow_record,
)

# ===========================================================================
# Digest binding + required-covered completeness
# ===========================================================================


def test_issued_records_bind_their_canonical_digest() -> None:
    """(§2/§3.1) Issuance computes the digest over the covered content and verifies it."""
    for record in (issue_authorization(), issue_workflow_record()):
        assert record.status is ArtifactStatus.ISSUED
        assert record.canonical_digest is not None
        assert record.missing_required_fields() == []


def test_a_substituted_digest_is_unconstructable() -> None:
    """(§4.1) Digest substitution fails at construction — the artifact cannot exist."""
    issued = issue_authorization()
    payload = issued.model_dump() | {"canonical_digest": "forged-digest"}
    with pytest.raises((ArtifactIntegrityError, ValidationError)):
        ReplacementAuthorization(**payload)


def test_a_tampered_covered_field_breaks_the_digest_binding() -> None:
    """(§4.1) Editing covered content while keeping the old digest is unconstructable."""
    issued = issue_authorization()
    payload = issued.model_dump() | {"scope_identity": "another-scope"}
    with pytest.raises((ArtifactIntegrityError, ValidationError)):
        ReplacementAuthorization(**payload)


def test_changing_any_covered_field_changes_the_digest() -> None:
    """(§2.3) Covered content is genuinely covered — a different mode is different bytes."""
    a = issue_authorization(replacement_mode=ReplacementMode.OVERLAP_FIRST)
    b = issue_authorization(replacement_mode=ReplacementMode.CANCEL_FIRST)
    assert a.canonical_digest != b.canonical_digest


def test_self_excluded_fields_do_not_change_the_digest() -> None:
    """(§2.3 self-exclusion) Ledger placement is excluded from the digest preimage."""
    a = issue_authorization(authorization_order=1)
    b = issue_authorization(authorization_order=99)
    assert a.canonical_digest == b.canonical_digest


def test_a_tbd_required_covered_field_blocks_issuance() -> None:
    """(§2.3) The reserved ``"TBD"`` placeholder is not a concrete value.

    A required-covered path left ``"TBD"`` (or ``None``) keeps the artifact pre-issuance:
    ``issue`` refuses, and the DRAFT itself reports the unmet path.
    """
    with pytest.raises((ArtifactIntegrityError, ValidationError)):
        issue_authorization(profile_version="TBD")
    draft = ReplacementAuthorization(
        authorization_id="repl-auth-draft",
        authorization_generation=1,
        workflow_id="repl-wf-1",
        scope_identity="scope-1",
        replacement_mode=ReplacementMode.OVERLAP_FIRST,
        profile_version="TBD",
    )
    assert draft.status is ArtifactStatus.DRAFT
    assert "profile_version" in draft.missing_required_fields()


def test_records_are_frozen_and_have_no_mutation_method() -> None:
    """(§2/§4.4) Append-only at the record level: no update / delete / transmit method."""
    record = issue_workflow_record()
    with pytest.raises(ValidationError):
        record.workflow_generation = 99  # type: ignore[misc]
    for forbidden in (
        "transmit",
        "send",
        "commit",
        "release_capacity",
        "remove_protection",
        "mutate",
        "update",
        "delete",
        "set_state",
    ):
        assert not hasattr(record, forbidden), (
            f"{forbidden}() exists on a workflow record — design #18 §4.4 requires the "
            "constructive absence of any transmit / mutate / commit path"
        )


def test_extra_fields_are_forbidden() -> None:
    """(§2) ``extra="forbid"`` is the schema-level seal against a silent unknown field."""
    with pytest.raises(ValidationError):
        ReplacementAuthorization(unexpected_field="x")  # type: ignore[call-arg]


# ===========================================================================
# Forgery / contradiction detection (id != f(digest))
# ===========================================================================


def test_same_id_different_bytes_authorization_is_a_critical_conflict() -> None:
    """(§0.4e forgery) A contradictory re-issuance under one id is CRITICAL_CONFLICT."""
    a = issue_authorization(replacement_mode=ReplacementMode.OVERLAP_FIRST)
    b = issue_authorization(replacement_mode=ReplacementMode.CANCEL_FIRST)
    assert a.authorization_id == b.authorization_id
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(
            a.authorization_id,
            a.canonical_digest,
            b.authorization_id,
            b.canonical_digest,
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_same_id_different_bytes_workflow_record_is_a_double_commit_conflict() -> None:
    """(§0.4e forgery) Two different workflow states under one record id conflict."""
    a = issue_workflow_record(workflow_state=ReplacementWorkflowState.COMPLETED)
    b = issue_workflow_record(workflow_state=ReplacementWorkflowState.FAILED_CONTAINED)
    assert a.record_id == b.record_id
    assert (
        classify_record_pair(
            a.record_id, a.canonical_digest, b.record_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_a_legitimate_new_generation_is_not_a_conflict() -> None:
    """(both ways) A fresh id + generation is a lawful re-issuance, not a forgery.

    §7 line 201 material change ⇒ re-evaluation ⇒ a **new generation**, never an in-place
    edit. If every re-issuance were flagged, the detector would be useless.
    """
    a = issue_authorization(authorization_id="repl-auth-1", authorization_generation=1)
    b = issue_authorization(authorization_id="repl-auth-2", authorization_generation=2)
    assert (
        classify_record_pair(
            a.authorization_id,
            a.canonical_digest,
            b.authorization_id,
            b.canonical_digest,
        )
        is not RecordPairKind.CRITICAL_CONFLICT
    )


def test_identical_bytes_under_one_id_is_not_a_conflict() -> None:
    """(both ways) An idempotent redelivery of the same record is not a contradiction."""
    a = issue_authorization()
    b = issue_authorization()
    assert a.canonical_digest == b.canonical_digest
    assert (
        classify_record_pair(
            a.authorization_id,
            a.canonical_digest,
            b.authorization_id,
            b.canonical_digest,
        )
        is not RecordPairKind.CRITICAL_CONFLICT
    )


# ===========================================================================
# label-grants-nothing (§5 line 137) + no-collapse (§5 line 107)
# ===========================================================================


@given(state=WORKFLOW_STATES)
def test_no_workflow_label_grants_any_authority(
    state: ReplacementWorkflowState,
) -> None:
    """(§5 line 137, all 9 states incl. ``COMPLETED``) A label authorizes nothing."""
    record = issue_workflow_record(workflow_state=state)
    assert workflow_label_grants_nothing(record.authority_effect) is True
    for flag in ReplacementAuthorityEffect.model_fields:
        assert getattr(record.authority_effect, flag) is False


def test_any_true_authority_flag_is_unconstructable() -> None:
    """(§5 line 137, type-level seal) A ``True`` flag makes the block unconstructable."""
    for flag in ReplacementAuthorityEffect.model_fields:
        with pytest.raises((ArtifactIntegrityError, ValidationError)):
            ReplacementAuthorityEffect(**{flag: True})


@given(forged=st.sampled_from(FORGED_AUTHORITY_VALUES))
def test_a_model_construct_forged_authority_flag_is_caught_by_the_recheck(
    forged: object,
) -> None:
    """(defence in depth) ``model_construct`` skips validators; the re-check does not.

    Note the re-check is ``is False``, not ``is not True``: a forged ``1`` / ``"yes"`` /
    ``[1]`` is truthy but is not ``True``, so an ``is not True`` re-check would clear it.
    """
    forged_block = ReplacementAuthorityEffect.model_construct(releases_capacity=forged)
    assert workflow_label_grants_nothing(forged_block) is False


def test_an_absent_authority_block_is_not_a_pass() -> None:
    """(§4.7 row 12) A missing authority block is unknown, not all-false."""
    assert workflow_label_grants_nothing(None) is False
    # (b) passing side — a genuine all-false block passes.
    assert workflow_label_grants_nothing(ReplacementAuthorityEffect()) is True


def test_the_five_orthogonal_axes_stay_separate_fields() -> None:
    """(§5 line 107) order / transmission / knowledge / capacity / protection: 5 fields."""
    record = issue_workflow_record()
    assert workflow_record_axes_not_collapsed(record) is True
    assert workflow_record_axes_not_collapsed(None) is False
    # The five axes carry *different* injected tokens simultaneously — a single collapsed
    # enum could not represent this state at all.
    assert record.broker_order_state == "WORKING"
    assert record.transmission_attempt_state == "SENT_UNCONFIRMED"
    assert record.knowledge_confidence == "PARTIAL"
    assert record.capacity_state == "COMMITTED"
    assert record.protection_state == "PROTECTED"
    assert record.workflow_state is ReplacementWorkflowState.INTERMEDIATE_STATE


# ===========================================================================
# Append-only generation ordering (tos.ordering REUSE, §3.2)
# ===========================================================================


def test_workflow_generations_order_by_the_core_ordering_law() -> None:
    """(§3.2) Ordering comes from ``tos.ordering``; no new ordering law is authored."""
    first = issue_workflow_record(record_id="rec-1", workflow_generation=1)
    second = issue_workflow_record(record_id="rec-2", workflow_generation=2)
    assert workflow_generation_order(first, second).value == "BEFORE"
    assert workflow_generation_order(second, first).value == "AFTER"


def test_records_from_different_workflows_are_ambiguous_not_ordered() -> None:
    """(§3.2) A native sequence orders only inside one continuity — never across."""
    a = issue_workflow_record(
        record_id="rec-a", workflow_id="wf-a", workflow_generation=1
    )
    b = issue_workflow_record(
        record_id="rec-b", workflow_id="wf-b", workflow_generation=2
    )
    assert workflow_generation_order(a, b).value == "AMBIGUOUS"


def test_a_missing_generation_is_ambiguous_not_an_assumed_precedence() -> None:
    """(fail-closed) An unordered record is never silently placed."""
    known = issue_workflow_record(record_id="rec-1", workflow_generation=1)
    unknown = ReplacementWorkflowRecord(workflow_id="repl-wf-1")
    assert workflow_generation_order(known, unknown).value == "AMBIGUOUS"


def test_append_only_requires_strictly_increasing_concrete_generations() -> None:
    """(§2.3) A repeated / decreasing / absent generation breaks the append-only claim."""
    ok = [
        issue_workflow_record(record_id="r1", workflow_generation=1),
        issue_workflow_record(record_id="r2", workflow_generation=2),
        issue_workflow_record(record_id="r3", workflow_generation=5),
    ]
    assert workflow_generation_append_only(ok) is True
    repeated = [ok[0], issue_workflow_record(record_id="r2", workflow_generation=1)]
    assert workflow_generation_append_only(repeated) is False
    decreasing = [ok[1], ok[0]]
    assert workflow_generation_append_only(decreasing) is False
    absent = [ReplacementWorkflowRecord(workflow_id="repl-wf-1")]
    assert workflow_generation_append_only(absent) is False
    assert workflow_generation_append_only([]) is True


# ===========================================================================
# Injected-bound discipline (§8 — nothing numeric is defaulted)
# ===========================================================================


def test_protection_obligation_bounds_default_to_none_not_to_a_number() -> None:
    """(§8 / ADR §15 line 353) A missing bound is UNKNOWN, never a hardcoded default."""
    obligation = ProtectionObligation()
    assert obligation.max_protection_gap is None
    assert obligation.max_protection_overlap is None
    assert obligation.protected_quantity is None


def test_canonical_decimal_rejects_nan_and_infinity() -> None:
    """(§3.1) NaN / infinity magnitudes are unconstructable, so a digest cannot drift."""
    for bad in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(ValidationError):
            ProtectionObligation(protected_quantity=bad)


def test_canonical_decimal_normalizes_scale_so_one_point_zero_shares_a_digest() -> None:
    """(§3.1) ``1.0`` and ``1.00`` must not produce two different artifact digests."""
    a = issue_authorization(
        protection_obligation=ProtectionObligation(protected_quantity=Decimal("1.0"))
    )
    b = issue_authorization(
        protection_obligation=ProtectionObligation(protected_quantity=Decimal("1.00"))
    )
    assert a.canonical_digest == b.canonical_digest


# ===========================================================================
# _ID_FIELD drift lock (design #18 §2.3/§3.1 — the independent-id contract)
# ===========================================================================


def test_the_id_field_declarations_name_the_real_independent_id_fields() -> None:
    """(§3.1) ``_ID_FIELD`` must name the actual id field on each record.

    The whole ``id != f(digest)`` forgery-detection story rests on this pointer: if
    ``_ID_FIELD`` drifted to another field name, ``issue`` would blank the wrong attribute
    and the same-id / different-bytes conflict would stop being representable. The set
    assertions elsewhere in this module are invariant under that drift, so it is pinned
    explicitly here.
    """
    assert ReplacementAuthorization._ID_FIELD == "authorization_id"
    assert ReplacementWorkflowRecord._ID_FIELD == "record_id"
    for model in (ReplacementAuthorization, ReplacementWorkflowRecord):
        assert (
            model._ID_FIELD in model.model_fields
        ), f"{model.__name__}._ID_FIELD names a field that does not exist"


def test_the_independent_id_is_excluded_from_the_digest_preimage() -> None:
    """(§2.3 self-exclusion) ``id != f(digest)`` requires the id **outside** the preimage.

    If the id were covered, a re-issuance under a new id would produce different bytes for
    structurally identical content and every lawful re-issuance would look like a
    contradiction — and, worse, the id and the digest would stop being orthogonal, which is
    precisely what makes a same-id / different-bytes forgery detectable (design #18 §0.4e).
    """
    for model in (ReplacementAuthorization, ReplacementWorkflowRecord):
        assert model._ID_FIELD not in model._COVERED_FIELDS, (
            f"{model.__name__}._ID_FIELD is inside _COVERED_FIELDS — id and digest are no "
            "longer orthogonal, so CRITICAL_CONFLICT detection is defeated"
        )
    # Behavioural corollary: two records that differ **only** by id share a digest, which
    # is what lets classify_record_pair separate "same id, different bytes" (a forgery)
    # from "different id, same bytes" (a lawful re-issuance).
    a = issue_authorization(authorization_id="repl-auth-A")
    b = issue_authorization(authorization_id="repl-auth-B")
    assert a.authorization_id != b.authorization_id
    assert a.canonical_digest == b.canonical_digest


def test_ledger_placement_fields_are_also_outside_the_preimage() -> None:
    """(§2.3) Ledger placement is a Layer-2 back-reference, never covered content."""
    assert "authorization_order" not in ReplacementAuthorization._COVERED_FIELDS
    assert "record_order" not in ReplacementWorkflowRecord._COVERED_FIELDS
    assert "authority_effect" not in ReplacementAuthorization._COVERED_FIELDS
    assert "authority_effect" not in ReplacementWorkflowRecord._COVERED_FIELDS
