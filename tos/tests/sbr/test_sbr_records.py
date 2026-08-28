"""sbr record models — id ⊥ digest, content-addressing, all-false authority (design #17 §2).

Regime tag: predicate / model substrate only; SBR-EV-001..012 NOT_IMPLEMENTED; EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tos.canonical import RecordPairKind, classify_record_pair
from tos.sbr import (
    ObligationResult,
    ReadinessVerdict,
    RecoveryAuthorityEffect,
    RecoveryEvidencePackage,
    RecoveryInventoryCut,
    RecoveryObligation,
    RecoveryObligationGraph,
    RecoverySession,
    RecoveryTrigger,
    SessionState,
)

from ._sbr_strategies import SCHEME, issue_decision, issue_session, obligation


def test_session_is_issued_with_independent_id() -> None:
    """(§3.1) A session carries a concrete id ⊥ digest and a verified canonical digest."""
    session = issue_session()
    assert session.session_id == "sbr-sess-1"
    assert session.canonical_digest is not None
    assert session.session_id != session.canonical_digest
    assert session.state is SessionState.READY


def test_readiness_decision_id_is_orthogonal_to_digest() -> None:
    """(§2.1) decision_id is independent of the canonical digest (id ⊥ digest)."""
    decision = issue_decision()
    assert decision.decision_id == "sbr-dec-1"
    assert decision.canonical_digest is not None
    assert decision.decision_id != decision.canonical_digest
    assert decision.verdict is ReadinessVerdict.READY


def test_same_id_different_bytes_is_a_critical_conflict() -> None:
    """(§2.1) A readiness substitution (same id, different bytes) is a detectable CRITICAL_CONFLICT."""
    original = issue_decision(recovery_generation=3, verdict=ReadinessVerdict.READY)
    substituted = issue_decision(
        recovery_generation=99, verdict=ReadinessVerdict.NOT_READY
    )
    assert original.decision_id == substituted.decision_id
    assert original.canonical_digest != substituted.canonical_digest
    kind = classify_record_pair(
        original.decision_id,
        original.canonical_digest,
        substituted.decision_id,
        substituted.canonical_digest,
    )
    assert kind is RecordPairKind.CRITICAL_CONFLICT


def test_trigger_and_cut_are_content_addressed() -> None:
    """(§2.1) The same trigger / cut content yields the same canonical digest (content-addressed)."""
    a = RecoveryTrigger.issue(
        scheme=SCHEME,
        trigger_id="t1",
        trigger_class="COLD_START",
        recovery_generation=1,
    )
    b = RecoveryTrigger.issue(
        scheme=SCHEME,
        trigger_id="t1",
        trigger_class="COLD_START",
        recovery_generation=1,
    )
    assert a.canonical_digest == b.canonical_digest
    c = RecoveryInventoryCut.issue(scheme=SCHEME, session_id="s", recovery_generation=1)
    d = RecoveryInventoryCut.issue(scheme=SCHEME, session_id="s", recovery_generation=1)
    assert c.canonical_digest == d.canonical_digest


def test_evidence_package_issues_and_self_excludes_its_digest() -> None:
    """(§2.3) The package issues with an independent id and a verified digest."""
    package = RecoveryEvidencePackage.issue(
        scheme=SCHEME,
        package_id="pk-1",
        session_id="s1",
        recovery_generation=3,
        inventory_cut_digest="ic",
        manifest_digests=("m1", "m2"),
    )
    assert package.package_id == "pk-1"
    assert package.canonical_digest is not None
    assert package.package_id != package.canonical_digest


def test_all_false_authority_effect_rejects_any_true_flag() -> None:
    """(SBR-INV-003) Any True authority flag makes RecoveryAuthorityEffect unconstructable."""
    assert RecoveryAuthorityEffect().creates_capacity is False
    for field in (
        "creates_capacity",
        "issues_live_auth",
        "issues_capability",
        "classifies_protective",
        "transmits_broker",
        "grants_rearm",
    ):
        with pytest.raises(ValidationError):
            RecoveryAuthorityEffect(**{field: True})


def test_session_and_decision_carry_all_false_authority() -> None:
    """(SBR-INV-003 / §16 line 424) A session / decision creates no authority."""
    session = issue_session()
    decision = issue_decision()
    for flag in (
        session.authority_effect.creates_capacity,
        session.authority_effect.grants_rearm,
        decision.authority_effect.issues_live_auth,
        decision.authority_effect.transmits_broker,
    ):
        assert flag is False


def test_frozen_models_reject_mutation() -> None:
    """(§2.0/§4.6) Every record is frozen — there is no in-place mutate path."""
    decision = issue_decision()
    with pytest.raises(ValidationError):
        decision.verdict = ReadinessVerdict.NOT_READY  # type: ignore[misc]


def test_extra_fields_are_forbidden() -> None:
    """(§4.7) extra='forbid' — an unknown field is restrictive, never silently dropped."""
    with pytest.raises(ValidationError):
        RecoverySession(session_id="s", recovery_generation=1, unknown_field=True)  # type: ignore[call-arg]


def test_obligation_graph_container_exposes_frozenset_view() -> None:
    """(§13) The obligation graph container yields the obligation set for the closure predicate."""
    graph = RecoveryObligationGraph(
        obligations=(obligation("a"), obligation("b", prerequisites=("a",)))
    )
    obligation_set = graph.obligation_set()
    assert len(obligation_set) == 2
    assert all(isinstance(o, RecoveryObligation) for o in obligation_set)


def test_obligation_holds_acceptable_results_and_result() -> None:
    """(§13 line 346) An obligation carries its acceptable-result set and terminal result."""
    obl = obligation("x", result=ObligationResult.SATISFIED)
    assert obl.result is ObligationResult.SATISFIED
    assert ObligationResult.SATISFIED in obl.acceptable_results
