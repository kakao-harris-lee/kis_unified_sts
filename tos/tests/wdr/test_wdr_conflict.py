"""Same-id / different-covered-bytes conflict regression for the five artifacts (design #26 §2.1/§3.1).

Every wdr digest-bound artifact (``SafetyDeviationPolicy`` / ``SafetyDeviationRequest`` /
``SafetyDeviationDecision`` / ``ResidualRiskAcceptanceRecord`` / ``ActiveDeviationSet``) is an
:class:`~tos.canonical.IndependentIdArtifact` (``id != f(digest)``): the id is separately issued, so a
same-id / different-**covered**-bytes forgery, re-issue, or replay is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (design #26 §2.1/§3.1 — WDR-EV-001/012). A flip of a
**non-covered** lifecycle coordinate (``single_use_consumed``) leaves the covered digest unchanged and
is an ``IDEMPOTENT_DUP``, never a false conflict (the coordinate-non-collapse precedent, §2.3/§4.4).

Regime tag: structural substrate; WDR-EV-001/012 NOT_IMPLEMENTED; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.wdr import RecordPairKind, classify_record_pair

from ._wdr_strategies import (
    clean_acceptance,
    clean_active_set,
    clean_decision,
    clean_policy,
    clean_request,
)


def test_policy_same_id_different_bytes_is_critical_conflict() -> None:
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


def test_request_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1) Two same-id requests with different covered bytes ⇒ CRITICAL_CONFLICT."""
    a = clean_request(request_id="req-x", request_version=1)
    b = clean_request(request_id="req-x", request_version=2)
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(
            a.request_id, a.canonical_digest, b.request_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_decision_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1) Two same-id decisions with different covered bytes ⇒ CRITICAL_CONFLICT."""
    a = clean_decision(decision_id="dec-x", decision_generation=1)
    b = clean_decision(decision_id="dec-x", decision_generation=2)
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(
            a.decision_id, a.canonical_digest, b.decision_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_acceptance_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1) Two same-id acceptance records with different covered bytes ⇒ CRITICAL_CONFLICT."""
    a = clean_acceptance(acceptance_id="acc-x", acceptance_generation=1)
    b = clean_acceptance(acceptance_id="acc-x", acceptance_generation=2)
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(
            a.acceptance_id, a.canonical_digest, b.acceptance_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_active_set_same_id_different_bytes_is_critical_conflict() -> None:
    """(§3.1) Two same-id active sets with different covered bytes ⇒ CRITICAL_CONFLICT."""
    a = clean_active_set(active_set_id="set-x", active_set_generation=1)
    b = clean_active_set(active_set_id="set-x", active_set_generation=2)
    assert a.canonical_digest != b.canonical_digest
    assert (
        classify_record_pair(
            a.active_set_id, a.canonical_digest, b.active_set_id, b.canonical_digest
        )
        is RecordPairKind.CRITICAL_CONFLICT
    )


def test_noncovered_single_use_flip_is_idempotent_dup_not_conflict() -> None:
    """(§2.3/§4.4 coordinate non-collapse) A single_use_consumed flip is excluded from the covered digest.

    ``single_use_consumed`` is a mutable lifecycle coordinate excluded from the covered digest, so a
    lawful consumption transition leaves the canonical digest unchanged — a same-id / same-bytes
    ``IDEMPOTENT_DUP``, never a mis-flagged ``CRITICAL_CONFLICT`` (the rcl / egress / cur / rlp
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


def test_noncovered_envelope_verdict_flip_is_idempotent_dup() -> None:
    """(§2.3 coordinate non-collapse) An injected spg combined-envelope verdict flip ⇒ IDEMPOTENT_DUP."""
    a = clean_active_set(active_set_id="set-x", combined_within_envelope=True)
    b = clean_active_set(active_set_id="set-x", combined_within_envelope=False)
    assert a.canonical_digest == b.canonical_digest
    assert (
        classify_record_pair(
            a.active_set_id, a.canonical_digest, b.active_set_id, b.canonical_digest
        )
        is RecordPairKind.IDEMPOTENT_DUP
    )


def test_pre_issuance_pair_is_not_comparable() -> None:
    """(canonical MINOR-1) A None-digest (pre-issuance) pair ⇒ NOT_COMPARABLE, never a false conflict."""
    a = clean_policy(policy_id="pol-x")
    assert (
        classify_record_pair(a.policy_id, None, a.policy_id, a.canonical_digest)
        is RecordPairKind.NOT_COMPARABLE
    )
