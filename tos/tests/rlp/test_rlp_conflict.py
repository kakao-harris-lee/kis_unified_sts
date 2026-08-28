"""Same-id / different-bytes conflict regression for the five digest-bound artifacts (§2.1/§3.1).

Every rlp digest-bound artifact (``TrialPolicy`` / ``ExactTrialPlan`` / ``TrialRun`` /
``TrialEvidencePackage`` / ``ProductionScopePromotionDecision``) is an
:class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``): the id is separately issued, so a
same-id / different-**covered**-bytes forgery, re-issue, or replay is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #25 §2.1/§3.1 — RLP-EV-001/007). A flip of a
**non-covered** lifecycle coordinate (``single_use_consumed``) leaves the covered digest unchanged and
is an ``IDEMPOTENT_DUP``, never a false conflict (the coordinate-non-collapse precedent, §2.3/§4.4).

Regime tag: structural substrate; RLP-EV-001/007 NOT_IMPLEMENTED; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.rlp import RecordPairKind, classify_record_pair

from ._rlp_strategies import (
    clean_decision,
    clean_package,
    clean_plan,
    clean_policy,
    clean_run,
)


def test_trial_policy_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1) Two same-id policies with different covered bytes ⇒ CRITICAL_CONFLICT (substitution seal)."""
    a = clean_policy(policy_id="pol-x", policy_generation=1)
    b = clean_policy(policy_id="pol-x", policy_generation=2)
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(
            a.policy_id, a.canonical_digest, b.policy_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_exact_trial_plan_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1) Two same-id plans with different covered bytes ⇒ CRITICAL_CONFLICT."""
    a = clean_plan(plan_id="plan-x", plan_generation=1)
    b = clean_plan(plan_id="plan-x", plan_generation=2)
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(
            a.plan_id, a.canonical_digest, b.plan_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_trial_run_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1) Two same-id runs with different covered bytes ⇒ CRITICAL_CONFLICT."""
    a = clean_run(run_id="run-x", run_generation=1)
    b = clean_run(run_id="run-x", run_generation=2)
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(a.run_id, a.canonical_digest, b.run_id, b.canonical_digest)
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_trial_evidence_package_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1) Two same-id packages with different covered bytes ⇒ CRITICAL_CONFLICT."""
    a = clean_package(package_id="pkg-x", package_generation=1)
    b = clean_package(package_id="pkg-x", package_generation=2)
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(
            a.package_id, a.canonical_digest, b.package_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_promotion_decision_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1) Two same-id promotion decisions with different covered bytes ⇒ CRITICAL_CONFLICT."""
    a = clean_decision(decision_id="dec-x", decision_generation=1)
    b = clean_decision(decision_id="dec-x", decision_generation=2)
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(
            a.decision_id, a.canonical_digest, b.decision_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_noncovered_single_use_flip_is_idempotent_dup_not_conflict() -> None:
    """(§2.3/§4.4 coordinate non-collapse) A single_use_consumed flip is excluded from the covered digest.

    ``single_use_consumed`` is a mutable lifecycle coordinate excluded from the covered digest, so a
    lawful consumption transition leaves the canonical digest unchanged — a same-id / same-bytes
    ``IDEMPOTENT_DUP``, never a mis-flagged ``CRITICAL_CONFLICT`` (the rcl / egress / cur
    coordinate-non-collapse precedent).
    """
    a = clean_decision(decision_id="dec-x", single_use_consumed=False)
    b = clean_decision(decision_id="dec-x", single_use_consumed=True)
    assert a.canonical_digest == b.canonical_digest
    assert (
        classify_record_pair(
            a.decision_id, a.canonical_digest, b.decision_id, b.canonical_digest
        )
        is RecordPairKind.IDEMPOTENT_DUP
    )
