"""MANDATED test-only seam cross-check: afg <-> orthostate (design #16 §3.4(d) / §6.1/§6.2)."""

from __future__ import annotations

from tos.afg import (
    ATTEMPT_STATE_SEND_FAILED_PROVEN,
    ATTEMPT_STATE_SENT_UNCONFIRMED,
    BROKER_ORDER_STATE_CANCELLED,
    BROKER_ORDER_STATE_UNKNOWN,
    cancel_ack_not_final_quantity_proof,
    no_blind_retry,
)
from tos.orthostate import BrokerOrderState, TransmissionAttemptState


def test_afg_attempt_tokens_equal_the_orthostate_members() -> None:
    """(drift lock) afg's attempt-state constants are the real enum values."""
    assert (
        TransmissionAttemptState.SENT_UNCONFIRMED.value
        == ATTEMPT_STATE_SENT_UNCONFIRMED
    )
    assert (
        TransmissionAttemptState.SEND_FAILED_PROVEN.value
        == ATTEMPT_STATE_SEND_FAILED_PROVEN
    )


def test_afg_broker_order_tokens_equal_the_orthostate_members() -> None:
    """(drift lock, m1) afg's broker-order constants are the real enum values."""
    assert BrokerOrderState.CANCELLED.value == BROKER_ORDER_STATE_CANCELLED
    assert BrokerOrderState.UNKNOWN.value == BROKER_ORDER_STATE_UNKNOWN


def test_orthostate_attempt_axis_has_exactly_one_positive_failure_proof() -> None:
    """(§14:350) ``SEND_FAILED_PROVEN`` is the only attempt state proving non-acceptance."""
    assert TransmissionAttemptState.SEND_FAILED_PROVEN in set(TransmissionAttemptState)
    for state in TransmissionAttemptState:
        permitted = no_blind_retry(
            state.value,
            BrokerOrderState.NONE_OBSERVED.value,
            True,
            5,
            complete_evidence_capability_coverage_authority=True,
            blind_failover_attempted=False,
        )
        assert permitted is (state is TransmissionAttemptState.SEND_FAILED_PROVEN), (
            f"{state} must {'permit' if state is TransmissionAttemptState.SEND_FAILED_PROVEN else 'deny'}"
            " a governed retry (§14 line 350)"
        )


def test_sent_unconfirmed_keeps_the_attempt_potentially_live() -> None:
    """(polarity -) A SENT_UNCONFIRMED attempt denies a retry (potentially live)."""
    assert (
        no_blind_retry(
            TransmissionAttemptState.SENT_UNCONFIRMED.value,
            BrokerOrderState.NONE_OBSERVED.value,
            True,
            5,
            complete_evidence_capability_coverage_authority=True,
            blind_failover_attempted=False,
        )
        is False
    )


def test_send_failed_proven_permits_a_governed_retry() -> None:
    """(polarity +, causal isolation) Only the attempt state changed => the verdict flips."""
    assert (
        no_blind_retry(
            TransmissionAttemptState.SEND_FAILED_PROVEN.value,
            BrokerOrderState.NONE_OBSERVED.value,
            True,
            5,
            complete_evidence_capability_coverage_authority=True,
            blind_failover_attempted=False,
        )
        is True
    )


def test_unknown_broker_order_state_denies_even_a_proven_send_failure() -> None:
    """(orthostate:118) UNKNOWN is capacity-consuming and never "safe to retry"."""
    assert (
        no_blind_retry(
            TransmissionAttemptState.SEND_FAILED_PROVEN.value,
            BrokerOrderState.UNKNOWN.value,
            True,
            5,
            complete_evidence_capability_coverage_authority=True,
            blind_failover_attempted=False,
        )
        is False
    )


def _cancel(state: str | None, **overrides: object) -> bool:
    base: dict[str, object] = {
        "final_quantity_proof_present": False,
        "original_and_replacement_covered": True,
        "capacity_release_claimed": True,
        "replacement_reuse_claimed": False,
        "retry_claimed": False,
    }
    base.update(overrides)
    return cancel_ack_not_final_quantity_proof(state, **base)  # type: ignore[arg-type]


def test_locally_observed_cancelled_does_not_release_capacity() -> None:
    """(polarity - §15:358) A CANCELLED broker-order state does not justify a release."""
    assert _cancel(BrokerOrderState.CANCELLED.value) is False


def test_a_separate_final_quantity_proof_flips_the_verdict() -> None:
    """(polarity +, causal isolation) Only the FQP flag changed => the release is justified."""
    assert (
        _cancel(BrokerOrderState.CANCELLED.value, final_quantity_proof_present=True)
        is True
    )


def test_later_fill_after_cancelled_is_why_cancel_ack_is_not_fqp() -> None:
    """(§15:358 rationale) orthostate accepts a later valid fill after a local CANCELLED."""
    assert BrokerOrderState.PARTIALLY_FILLED in set(BrokerOrderState)
    assert BrokerOrderState.FILLED in set(BrokerOrderState)
    for state in (BrokerOrderState.CANCELLED, BrokerOrderState.UNKNOWN):
        assert _cancel(state.value) is False
