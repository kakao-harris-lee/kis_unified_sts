"""Malformed-model self-defence — positive-claim + incomplete-structure seals (design #28 §2.3).

The #20 lesson: a positive claim coexisting with an incomplete structure must be **unconstructable**,
and because ``pydantic.BaseModel.model_construct`` skips validators, the same fact must be re-derived in
the predicate layer (two layers). Three artifacts carry a construction-time coexistence seal
(``IncidentClosureDecision`` / ``ActiveSafetyIncidentSet`` / ``SafetyIncidentRecord``) plus the
``ActiveSetMember`` structural seal that replaced v1.0's parallel tuples (C2-2).

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import pytest
import tos.sir as s

from ._sir_strategies import (
    CLEAN_APPLICABLE_INCIDENTS,
    CLEAN_APPLICABLE_SHARED_CAUSES,
    clean_active_set,
    clean_closure_decision,
    clean_contract_items,
    clean_dependency_closure,
    clean_member,
    clean_record,
    clean_scope,
)

_RAISES = (s.ArtifactIntegrityError, ValueError)


# --- IncidentClosureDecision: administrative closure binds exactly ----------


def test_administrative_closure_without_an_active_set_digest_is_unconstructable() -> (
    None
):
    """(§2.3 / §5.10 line 146) CLOSE_ADMINISTRATIVELY with a blank exact set digest cannot exist."""
    with pytest.raises(_RAISES):
        clean_closure_decision(active_set_digest=None)


def test_administrative_closure_with_a_short_contract_is_unconstructable() -> None:
    """(§2.3 / §20 line 490) CLOSE_ADMINISTRATIVELY with fewer than twelve items cannot exist."""
    with pytest.raises(_RAISES):
        clean_closure_decision(closure_contract_items=clean_contract_items()[:11])


def test_administrative_closure_with_a_long_contract_is_unconstructable() -> None:
    """(§2.3 both-ways) A surplus thirteenth contract item is equally unconstructable."""
    with pytest.raises(_RAISES):
        clean_closure_decision(closure_contract_items=(*clean_contract_items(), True))


def test_administrative_closure_with_an_unknown_item_is_unconstructable() -> None:
    """(§2.3 / SIR-INV-009) An unknown (``None``) contract item is not a satisfied item."""
    items = list(clean_contract_items())
    items[5] = None
    with pytest.raises(_RAISES):
        clean_closure_decision(closure_contract_items=tuple(items))


def test_denial_decisions_skip_the_seal_and_stay_non_permissive() -> None:
    """(§2.3 scope) The seal binds administrative closure only — a DENY / HOLD record is lawful.

    §5.10 binds every result to one exact incident and Active Safety Incident Set digest, so the
    ``_REQUIRED_COVERED`` identity still applies; what the coexistence seal adds for
    ``CLOSE_ADMINISTRATIVELY`` alone is the complete 12-item contract.
    """
    for denial in (s.ClosureDecisionResult.DENY, s.ClosureDecisionResult.HOLD):
        decision = clean_closure_decision(result=denial, closure_contract_items=())
        assert s.closure_administrative_non_permissive(decision) is False


def test_model_construct_closure_bypass_is_caught_by_the_predicate() -> None:
    """(2-layer §2.3) A ``model_construct`` malformed closure is re-caught in the predicate layer."""
    forged = s.IncidentClosureDecision.model_construct(
        closure_id="clo-forged",
        closure_generation=1,
        incident_id="inc-open",
        active_set_digest=None,
        incident_generation=5,
        result=s.ClosureDecisionResult.CLOSE_ADMINISTRATIVELY,
        closure_contract_items=(),
        effective_principal_verdict=True,
        single_use_consumed=False,
        consumed_by_live_authority=False,
        authority_effect=s.AllFalseIncidentAuthority(),
    )
    assert s.closure_administrative_non_permissive(forged) is False


# --- ActiveSafetyIncidentSet: exact identity + member structure -------------


def test_complete_claim_without_a_generation_is_unconstructable() -> None:
    """(§2.3 / §5.5 line 126) A complete claim with no Incident Generation cannot exist."""
    with pytest.raises(_RAISES):
        clean_active_set(is_complete=True, incident_generation=None)


def test_current_claim_without_a_safety_cell_is_unconstructable() -> None:
    """(§2.3 / §5.5 line 126 "an exact Safety Cell") A current claim with no cell cannot exist."""
    with pytest.raises(_RAISES):
        clean_active_set(is_current=True, safety_cell=None)


def test_duplicate_member_id_is_unconstructable() -> None:
    """(C2-2 structural seal) One canonical set represents each incident exactly once."""
    with pytest.raises(_RAISES):
        clean_active_set(
            members=(
                clean_member(incident_id="inc-open"),
                clean_member(incident_id="inc-open"),
            )
        )


def test_dangling_parent_is_unconstructable() -> None:
    """(C2-2 structural seal) A parent that is not a member would hide an open parent."""
    with pytest.raises(_RAISES):
        clean_active_set(
            members=(
                clean_member(incident_id="inc-open", parent_id="inc-ghost"),
                clean_member(
                    incident_id="inc-closed",
                    lifecycle_state=s.IncidentLifecycleState.CLOSED,
                ),
            )
        )


def test_shared_cause_outside_the_declared_dependencies_is_unconstructable() -> None:
    """(C2-2 structural seal / §5.5 line 126) Every shared cause is represented by the set."""
    with pytest.raises(_RAISES):
        clean_active_set(
            members=(
                clean_member(
                    incident_id="inc-open",
                    shared_cause_ids=frozenset({"dep-unrepresented"}),
                ),
                clean_member(
                    incident_id="inc-closed",
                    lifecycle_state=s.IncidentLifecycleState.CLOSED,
                ),
            ),
            shared_dependencies=("dep-shared",),
        )


def test_model_construct_duplicate_member_is_caught_by_the_predicate() -> None:
    """(2-layer §2.3) A ``model_construct`` duplicate member is re-caught by the union predicate."""
    forged = s.ActiveSafetyIncidentSet.model_construct(
        members=(
            clean_member(incident_id="inc-open"),
            clean_member(incident_id="inc-open"),
        ),
        shared_dependencies=(),
        is_complete=True,
        is_current=True,
        incident_generation=5,
        active_set_generation=1,
        safety_cell="cell-1",
    )
    assert s.active_set_is_canonical_union(forged, frozenset({"inc-open"})) is False
    assert (
        s.scope_exact_combined_no_favorable_subset(
            forged,
            clean_dependency_closure(),
            frozenset({"inc-open"}),
            CLEAN_APPLICABLE_SHARED_CAUSES,
            frozenset(),
        )
        is False
    )


# --- SafetyIncidentRecord: declared record has an exact scope --------------


def test_declared_record_without_an_exact_scope_is_unconstructable() -> None:
    """(§2.3 / §8 step 2) A record past SUSPECTED with no exact scope cannot exist."""
    for state in (
        s.IncidentLifecycleState.DECLARED,
        s.IncidentLifecycleState.CONTAINING,
        s.IncidentLifecycleState.ELIGIBLE_FOR_CLOSURE,
        s.IncidentLifecycleState.CLOSED,
    ):
        with pytest.raises(_RAISES):
            clean_record(lifecycle_state=state, incident_scope=None)


def test_suspected_record_may_still_lack_an_exact_scope() -> None:
    """(§2.3 scope / §9 line 290) ``SUSPECTED`` is the pre-scope restrictive state — lawful, and denied.

    The seal must not over-reach: §9 line 290 makes ``SUSPECTED`` restrictive *for the greatest credible
    scope*, i.e. the state a signal enters **before** the §8 step 2 computation completes. The record is
    therefore constructible, and the declaration predicate denies it on the scope conjunct instead.
    """
    record = clean_record(
        lifecycle_state=s.IncidentLifecycleState.SUSPECTED, incident_scope=None
    )
    assert record.incident_scope is None
    assert s.scope_not_self_exempt_or_narrowed(record.incident_scope) is False


def test_record_with_an_exact_scope_is_constructable_at_every_state() -> None:
    """(both-ways) With an exact scope present, every lifecycle state constructs lawfully."""
    for state in s.IncidentLifecycleState:
        record = clean_record(lifecycle_state=state, incident_scope=clean_scope())
        assert record.lifecycle_state is state


# --- digest binding: same id / different covered bytes ---------------------


def test_same_id_different_bytes_is_a_critical_conflict() -> None:
    """(§3.1 / §22 line 536) A same-id / different-covered-bytes replay is a CRITICAL_CONFLICT."""
    original = clean_active_set()
    substituted = clean_active_set(shared_dependencies=("dep-shared", "dep-extra"))
    assert original.canonical_digest != substituted.canonical_digest
    assert (
        s.classify_record_pair(
            original.active_set_id,
            original.canonical_digest,
            substituted.active_set_id,
            substituted.canonical_digest,
        )
        is s.RecordPairKind.CRITICAL_CONFLICT
    )


def test_same_id_same_bytes_is_an_idempotent_duplicate() -> None:
    """(§3.1) A byte-identical re-issue of the same id is an idempotent duplicate, not a conflict."""
    first = clean_closure_decision()
    second = clean_closure_decision()
    assert (
        s.classify_record_pair(
            first.closure_id,
            first.canonical_digest,
            second.closure_id,
            second.canonical_digest,
        )
        is s.RecordPairKind.IDEMPOTENT_DUP
    )


def test_pre_issuance_pair_is_not_comparable() -> None:
    """(§3.1 canonical MINOR-1 discipline) A pre-issuance DRAFT never produces a false conflict."""
    issued = clean_record()
    assert (
        s.classify_record_pair(
            issued.incident_id, issued.canonical_digest, "inc-open", None
        )
        is s.RecordPairKind.NOT_COMPARABLE
    )


def test_mutable_coordinates_are_not_covered() -> None:
    """(§2.3 coordinate non-collapse) A lawful lifecycle / verdict change never changes the digest."""
    base = clean_closure_decision()
    consumed = clean_closure_decision(single_use_consumed=True)
    live_consumed = clean_closure_decision(consumed_by_live_authority=True)
    assert base.canonical_digest == consumed.canonical_digest
    assert base.canonical_digest == live_consumed.canonical_digest
    set_base = clean_active_set()
    set_moved = clean_active_set(state=s.IncidentLifecycleState.CLOSED, is_current=True)
    assert set_base.canonical_digest == set_moved.canonical_digest
    record_base = clean_record()
    record_moved = clean_record(record_state=s.IncidentRecordState.SUPERSEDED)
    assert record_base.canonical_digest == record_moved.canonical_digest


def test_external_reference_digest_is_covered() -> None:
    """(§2.3 digest rule) The external ``active_set_digest`` **is** covered — the binding is unforgeable."""
    base = clean_closure_decision()
    swapped = clean_closure_decision(active_set_digest="other-set-digest")
    assert base.canonical_digest != swapped.canonical_digest
    assert (
        s.classify_record_pair(
            base.closure_id,
            base.canonical_digest,
            swapped.closure_id,
            swapped.canonical_digest,
        )
        is s.RecordPairKind.CRITICAL_CONFLICT
    )


def test_required_covered_fields_are_concrete_on_every_issued_artifact() -> None:
    """(§2.3 / canonical §3.2) Every issued artifact's ``_REQUIRED_COVERED`` paths are concrete."""
    for artifact in (
        clean_record(),
        clean_active_set(),
        clean_closure_decision(),
    ):
        assert artifact.missing_required_fields() == []
    assert (
        s.active_set_is_canonical_union(clean_active_set(), CLEAN_APPLICABLE_INCIDENTS)
        is True
    )
