"""afg five-artifact data model — digest binding, id ⊥ digest, all-false authority (§2).

Covers design #16 §2.1 (the digest-bound / value / REUSE classification), §2.3 (covered
content + self-exclusion + append-only generations), §0.4e (independent id, not
``f(digest)``), and §5.5 (the evidence-reconstruction substrate: a same-id / different-bytes
forged decision or double-spent permit is a ``classify_record_pair`` ``CRITICAL_CONFLICT``).

Closes **no** AFG-EV: predicate / coordinate substrate only (design #16 §1).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from pydantic import ValidationError
from tos.afg import (
    ActionFlowDecision,
    ActionFlowGovernorEffect,
    ActionFlowPermit,
    ActionFlowPolicy,
    ActionFlowResult,
    ActionFlowStateSnapshot,
    ActionFlowVector,
    AllFalseActionFlowAuthority,
    ArtifactStatus,
    decision_is_forward_only,
    governor_grants_no_authority,
)
from tos.canonical import RecordPairKind, classify_record_pair
from tos.rcl import CapacityVector

from ._afg_strategies import (
    FORGED_AUTHORITY_VALUES,
    REQUIRED_FIELD_TEXT,
    SCHEME,
    issue_decision,
    issue_permit,
    issue_policy,
    issue_snapshot,
)

_ARTIFACTS = (
    ActionFlowPolicy,
    ActionFlowStateSnapshot,
    ActionFlowDecision,
    ActionFlowPermit,
)


# ---------------------------------------------------------------------------
# §2.1 — the four digest-bound citizens + the ActionFlowVector REUSE
# ---------------------------------------------------------------------------


def test_four_artifacts_issue_with_verified_digests() -> None:
    """(§2.1) All four digest-bound artifacts issue and verify their canonical digest."""
    for artifact in (
        issue_policy(),
        issue_snapshot(),
        issue_decision(),
        issue_permit(),
    ):
        assert artifact.status is ArtifactStatus.ISSUED
        assert artifact.canonical_digest is not None
        assert artifact.missing_required_fields() == []


def test_action_flow_vector_is_the_rcl_capacity_vector_type() -> None:
    """(§0.4c) ``ActionFlowVector`` IS the rcl ``CapacityVector`` type — no self-authored vector."""
    assert ActionFlowVector is CapacityVector
    decision = issue_decision()
    assert isinstance(decision.action_flow_vector, CapacityVector)
    assert (
        ActionFlowDecision.model_fields["action_flow_vector"].annotation
        is CapacityVector
    )
    assert ActionFlowPermit.model_fields["resource_vector"].annotation is CapacityVector


def test_artifacts_are_frozen_and_have_no_mutating_method() -> None:
    """(§2.0/§4.6) Every artifact is frozen and exposes no consume / claim / transmit path."""
    forbidden = (
        "consume",
        "claim",
        "transmit",
        "send",
        "issue_capability",
        "mutate",
        "release",
        "rearm",
        "re_arm",
        "set_live_scope",
        "activate",
    )
    for cls in _ARTIFACTS:
        assert cls.model_config.get("frozen") is True
        assert cls.model_config.get("extra") == "forbid"
        for name in forbidden:
            assert not hasattr(cls, name), f"{cls.__name__} must not expose {name}()"


def test_extra_field_is_rejected() -> None:
    """(§2 / §8 line 248) ``extra="forbid"`` — an unknown field cannot be silently dropped."""
    with pytest.raises(ValidationError):
        ActionFlowPolicy(policy_id="x", unknown_field=1)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# §3.1 / §0.4e — independent id (id ⊥ digest) + CRITICAL_CONFLICT detection
# ---------------------------------------------------------------------------


@given(version=REQUIRED_FIELD_TEXT)
def test_policy_id_is_independent_of_the_digest(version: str) -> None:
    """(§3.1) Changing covered content changes the digest but never the independent id."""
    first = issue_policy(policy_version="v1")
    second = issue_policy(policy_version=version)
    assert first.policy_id == second.policy_id
    if version != "v1":
        assert first.canonical_digest != second.canonical_digest


def test_same_id_different_bytes_decision_is_a_critical_conflict() -> None:
    """(§5.5) A contradictory same-id decision is a detectable CRITICAL_CONFLICT."""
    granted = issue_decision(result=ActionFlowResult.GRANT)
    denied = issue_decision(result=ActionFlowResult.DENY)
    assert granted.decision_id == denied.decision_id
    assert granted.canonical_digest != denied.canonical_digest
    assert (
        classify_record_pair(
            granted.decision_id,
            granted.canonical_digest,
            denied.decision_id,
            denied.canonical_digest,
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_double_spend_permit_is_a_critical_conflict() -> None:
    """(§5.5) A same-id permit re-issued with a different nonce is a CRITICAL_CONFLICT."""
    first = issue_permit(claim_nonce="nonce-1")
    forged = issue_permit(claim_nonce="nonce-2")
    assert first.permit_id == forged.permit_id
    assert (
        classify_record_pair(
            first.permit_id,
            first.canonical_digest,
            forged.permit_id,
            forged.canonical_digest,
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_identical_reissue_is_not_a_conflict() -> None:
    """(both-ways) An identical re-issue is a benign duplicate, not a conflict."""
    a = issue_decision()
    b = issue_decision()
    assert (
        classify_record_pair(
            a.decision_id, a.canonical_digest, b.decision_id, b.canonical_digest
        )
        is not RecordPairKind.CRITICAL_CONFLICT
    )


def test_new_generation_gets_a_fresh_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """(§2.3) A legitimate revalidation is a NEW generation with a fresh id, not a mutation."""
    del monkeypatch
    gen1 = issue_policy(policy_id="afg-pol-1", policy_generation=1)
    gen2 = issue_policy(policy_id="afg-pol-2", policy_generation=2)
    assert gen1.policy_id != gen2.policy_id
    assert (
        classify_record_pair(
            gen1.policy_id,
            gen1.canonical_digest,
            gen2.policy_id,
            gen2.canonical_digest,
        )
        is not RecordPairKind.CRITICAL_CONFLICT
    )


def test_issued_artifact_requires_a_concrete_independent_id() -> None:
    """(§3.1) An ISSUED artifact with a null / "TBD" id is unconstructable."""
    for bad_id in (None, "TBD"):
        with pytest.raises(Exception) as excinfo:
            ActionFlowPolicy.issue(
                scheme=SCHEME,
                policy_id=bad_id,
                policy_generation=1,
                policy_version="v1",
            )
        assert "concrete policy_id" in str(excinfo.value)


# ---------------------------------------------------------------------------
# §2.3 — required covered / self-exclusion
# ---------------------------------------------------------------------------


def test_required_covered_is_structural_identity_only() -> None:
    """(§2.3) No numeric magnitude appears in any ``_REQUIRED_COVERED`` (null-bound ISSUED)."""
    numeric_ish = ("magnitude", "limit", "rate", "burst", "queue", "age", "vector")
    for cls in _ARTIFACTS:
        for field in cls._REQUIRED_COVERED:
            assert not any(token in field for token in numeric_ish), (
                f"{cls.__name__}._REQUIRED_COVERED contains numeric field {field!r} — "
                "a Phase-1 null bound would make the artifact unissuable (§2.3)"
            )


def test_ledger_placement_order_is_self_excluded_from_the_digest() -> None:
    """(§2.3/§3.2) The ``*_order`` ledger placement is not part of the digest preimage."""
    a = issue_decision(decision_order=1)
    b = issue_decision(decision_order=99)
    assert a.canonical_digest == b.canonical_digest


def test_missing_required_covered_blocks_issue() -> None:
    """(§2.3) A permit missing its claim nonce has an incomplete required-covered set."""
    draft = ActionFlowPermit(
        permit_id="afg-permit-1",
        permit_generation=1,
        command_identity="cmd-1",
        claim_nonce=None,
    )
    assert draft.status is ArtifactStatus.DRAFT
    assert "claim_nonce" in draft.missing_required_fields()


# ---------------------------------------------------------------------------
# §4.6 / AFG-INV-011 — all-false governor authority ("create" / "issue" verbs)
# ---------------------------------------------------------------------------


def test_default_governor_effect_grants_nothing() -> None:
    """(canary +) A default all-false governor effect grants nothing => True."""
    assert governor_grants_no_authority(ActionFlowGovernorEffect()) is True


def test_any_true_authority_flag_is_unconstructable() -> None:
    """(canary 'create/issue/transmit' AFG-INV-011) Any True flag makes the effect unconstructable."""
    for field in (
        "creates_capacity",
        "mutates_budget",
        "issues_authority",
        "permits_transmission",
        "holds_broker_credential",
        "may_rearm",
    ):
        with pytest.raises(ValidationError):
            ActionFlowGovernorEffect(**{field: True})


def test_snapshot_and_decision_and_permit_carry_all_false_authority() -> None:
    """(§5.3 line 121 / §5.5 line 129) Snapshot, decision, and permit grant no permission."""
    for artifact in (issue_snapshot(), issue_decision(), issue_permit()):
        assert governor_grants_no_authority(artifact.authority_effect) is True


def test_forged_unvalidated_authority_is_still_caught_by_the_predicate() -> None:
    """(defence in depth) ``model_construct`` skips validators — the predicate still says False."""
    forged = ActionFlowGovernorEffect.model_construct(permits_transmission=True)
    assert governor_grants_no_authority(forged) is False


def test_every_declared_authority_flag_is_covered_by_the_predicate() -> None:
    """(anti-under-realization) The predicate checks EVERY declared flag, not a fixed six.

    A hardcoded disjunction would silently stop covering a flag added later; this drives
    each declared field through the unvalidated ``model_construct`` path and requires the
    predicate to reject it.
    """
    declared = list(ActionFlowGovernorEffect.model_fields)
    assert declared, "the governor effect must declare at least one authority flag"
    for field in declared:
        forged = ActionFlowGovernorEffect.model_construct(**{field: True})
        assert (
            governor_grants_no_authority(forged) is False
        ), f"{field}=True must not be reported as granting no authority"


def test_forged_truthy_non_bool_authority_flag_is_rejected() -> None:
    """(M3 regression) A forged **truthy non-bool** flag must not clear the predicate.

    ``model_construct`` skips validators, so a forged block can carry any object. An
    ``is not True`` check would pass ``1`` / ``1.0`` / ``"yes"`` / ``[1]`` and report
    "grants no authority" for an artifact that plainly does — the predicate must demand a
    positive singleton ``False`` on every declared flag.
    """
    for field in ActionFlowGovernorEffect.model_fields:
        for forged_value in FORGED_AUTHORITY_VALUES:
            forged = ActionFlowGovernorEffect.model_construct(**{field: forged_value})
            assert governor_grants_no_authority(forged) is False, (
                f"{field}={forged_value!r} is a forged truthy authority claim and must "
                "not be reported as granting no authority"
            )


def test_unset_flags_on_a_constructed_block_keep_their_false_defaults() -> None:
    """(M3 boundary) ``model_construct()`` fills declared defaults, so omission is safe.

    Every flag defaults to ``False``, so a block built with no overrides really is
    all-false and legitimately passes — the forgery risk is an explicitly *supplied*
    non-``False`` value, which :func:`test_forged_truthy_non_bool_authority_flag_is_rejected`
    covers. Pinned here so a future default change (e.g. to ``None``) is caught.
    """
    forged = ActionFlowGovernorEffect.model_construct()
    for field in ActionFlowGovernorEffect.model_fields:
        assert getattr(forged, field) is False
    assert governor_grants_no_authority(forged) is True


def test_none_valued_authority_flag_is_not_a_proof_of_falsity() -> None:
    """(M3 regression) A forged ``None`` flag is neither ``True`` nor ``False`` => rejected.

    ``None`` is UNKNOWN: it does not positively establish that the authority is absent, so
    the ``is False`` gate must refuse it (an ``is not True`` gate would have cleared it).
    """
    for field in ActionFlowGovernorEffect.model_fields:
        forged = ActionFlowGovernorEffect.model_construct(**{field: None})
        assert governor_grants_no_authority(forged) is False


def test_empty_authority_fieldset_subclass_proves_nothing() -> None:
    """(anti-vacuity) A block declaring **no** flag is not a proof of authority separation.

    "Grants nothing over nothing" is vacuous: an all-false block with an empty field set
    would make :func:`governor_grants_no_authority` trivially ``True`` for an artifact that
    declares no separation at all.
    """

    class _EmptyEffect(AllFalseActionFlowAuthority):
        pass

    assert _EmptyEffect.model_fields == {}
    assert governor_grants_no_authority(_EmptyEffect()) is False  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# §5.3 / ADR §29 q2 — forward-only decision (non-cyclic)
# ---------------------------------------------------------------------------


def test_decision_is_forward_only() -> None:
    """(canary +) The decision carries no reservation / permit / claim coordinate."""
    assert decision_is_forward_only(issue_decision()) is True


def test_decision_model_lacks_every_forward_binding_field() -> None:
    """(§5.3) The decision structurally lacks bound_reservation_* / permit_id / claim_nonce."""
    fields = set(ActionFlowDecision.model_fields)
    for forbidden in (
        "bound_reservation_revision",
        "bound_reservation_digest",
        "bound_generation",
        "reservation_id",
        "permit_id",
        "claim_nonce",
    ):
        assert forbidden not in fields


def test_cyclic_binding_subclass_is_caught() -> None:
    """(canary -) A subclass reintroducing a reservation coordinate fails the structural check."""

    class CyclicDecision(ActionFlowDecision):
        bound_reservation_revision: int | None = None

    cyclic = CyclicDecision(decision_id="x", status=ArtifactStatus.DRAFT)
    assert decision_is_forward_only(cyclic) is False
