"""Core §5.5-§5.6 — replay / substitution + capability/permit single-use (design #22; EGRESS-EV-005).

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV-005 substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.egress import (
    ClaimObservation,
    RecordPairKind,
    capability_and_permit_single_use,
    replay_or_substitution_detected,
)

from ._egress_strategies import clean_replay_observation

# ---- §5.5 replay / substitution classification ---------------------------


def test_same_subject_different_bytes_is_critical_conflict() -> None:
    """(§5.5) Same proof/capability/nonce id + different request bytes ⇒ CRITICAL_CONFLICT."""
    a = clean_replay_observation(
        observation_id="o1", subject_identity="proof-1", bound_request_digest="bytes-A"
    )
    b = clean_replay_observation(
        observation_id="o2", subject_identity="proof-1", bound_request_digest="bytes-B"
    )
    assert replay_or_substitution_detected(a, b) is RecordPairKind.CRITICAL_CONFLICT


def test_same_subject_same_bytes_is_idempotent_replay() -> None:
    """(§5.5) Same subject + identical bytes ⇒ IDEMPOTENT_DUP (already-consumed replay)."""
    a = clean_replay_observation(
        observation_id="o1", subject_identity="proof-1", bound_request_digest="bytes-A"
    )
    b = clean_replay_observation(
        observation_id="o2", subject_identity="proof-1", bound_request_digest="bytes-A"
    )
    assert replay_or_substitution_detected(a, b) is RecordPairKind.IDEMPOTENT_DUP


def test_distinct_subjects_are_distinct() -> None:
    """(§5.5) Different subjects with different bytes ⇒ DISTINCT (no shared-identity conflict)."""
    a = clean_replay_observation(
        observation_id="o1", subject_identity="proof-1", bound_request_digest="bytes-A"
    )
    b = clean_replay_observation(
        observation_id="o2", subject_identity="proof-2", bound_request_digest="bytes-B"
    )
    assert replay_or_substitution_detected(a, b) is RecordPairKind.DISTINCT


def test_none_observation_is_not_comparable() -> None:
    """(§5.5 fail-safe) A None observation ⇒ NOT_COMPARABLE (never a false conflict)."""
    a = clean_replay_observation(observation_id="o1")
    assert replay_or_substitution_detected(None, a) is RecordPairKind.NOT_COMPARABLE
    assert replay_or_substitution_detected(a, None) is RecordPairKind.NOT_COMPARABLE


# ---- §5.6 capability / permit single-use ---------------------------------


def test_first_use_with_no_prior_claims_passes() -> None:
    """(§5.6) A first claim of both nonces (no prior claims) is single-use."""
    assert (
        capability_and_permit_single_use(
            "cap-1", "afp-1", [], principal="p-1", request_digest="rq-1"
        )
        is True
    )


def test_none_nonce_fails_closed() -> None:
    """(§5.6 fail-closed) A None capability / permit nonce fails single-use."""
    assert (
        capability_and_permit_single_use(
            None, "afp-1", [], principal="p-1", request_digest="rq-1"
        )
        is False
    )
    assert (
        capability_and_permit_single_use(
            "cap-1", None, [], principal="p-1", request_digest="rq-1"
        )
        is False
    )


def test_none_principal_or_request_fails_closed() -> None:
    """(§5.6 fail-closed) A None principal / request digest fails the bind."""
    assert (
        capability_and_permit_single_use(
            "cap-1", "afp-1", [], principal=None, request_digest="rq-1"
        )
        is False
    )
    assert (
        capability_and_permit_single_use(
            "cap-1", "afp-1", [], principal="p-1", request_digest=None
        )
        is False
    )


def test_reused_nonce_same_context_is_not_single_use() -> None:
    """(§5.6) A prior claim of the same nonce (same principal/request) is a replay ⇒ False."""
    prior = [ClaimObservation(nonce="cap-1", principal="p-1", request_digest="rq-1")]
    assert (
        capability_and_permit_single_use(
            "cap-1", "afp-1", prior, principal="p-1", request_digest="rq-1"
        )
        is False
    )


def test_transplanted_nonce_different_principal_is_rejected() -> None:
    """(§5.6 transplant) A prior claim of the same nonce by a DIFFERENT principal ⇒ False."""
    prior = [
        ClaimObservation(nonce="cap-1", principal="other-p", request_digest="rq-x")
    ]
    assert (
        capability_and_permit_single_use(
            "cap-1", "afp-1", prior, principal="p-1", request_digest="rq-1"
        )
        is False
    )


def test_permit_nonce_transplant_also_rejected() -> None:
    """(§5.6 transplant) A prior claim of the permit nonce elsewhere ⇒ False."""
    prior = [
        ClaimObservation(nonce="afp-1", principal="other-p", request_digest="rq-x")
    ]
    assert (
        capability_and_permit_single_use(
            "cap-1", "afp-1", prior, principal="p-1", request_digest="rq-1"
        )
        is False
    )


def test_unrelated_prior_claims_do_not_block() -> None:
    """(§5.6 both-ways) Prior claims of UNRELATED nonces do not block a fresh single-use claim."""
    prior = [
        ClaimObservation(nonce="other-nonce", principal="p-1", request_digest="rq-1")
    ]
    assert (
        capability_and_permit_single_use(
            "cap-1", "afp-1", prior, principal="p-1", request_digest="rq-1"
        )
        is True
    )
