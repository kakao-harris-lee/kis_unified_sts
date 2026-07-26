"""MANDATED test-only seam cross-check: afg <-> orthostate (design #16 §3.4(d) / §6.1/§6.2).

afg does **not** import ``tos.orthostate`` at runtime (the §7.1 allowlist closure test
asserts its absence); afg carries afg-local **coordinate constants** naming the orthostate
enum members it consumes by injection. This file imports **both** as a **test** to lock:

* token drift — the afg constants equal the real ``TransmissionAttemptState`` /
  ``BrokerOrderState`` member values (``vocabulary.py:61`` attempt, ``:92`` broker-order —
  design #16 m1 corrected the v1.0 line reference);
* polarity — ``SENT_UNCONFIRMED`` (``:86``) leaves the attempt **potentially live** and
  therefore denies a retry, while ``SEND_FAILED_PROVEN`` (``:88``) is the attempt-axis
  **positive** counterpart that permits a governed one (§14 line 350; AFG-INV-008);
* cancel polarity — a locally observed ``CANCELLED`` (``:115``) is not a Final Quantity
  Proof, because "a later valid fill SHALL be accepted even after a locally observed
  CANCELLED", and ``UNKNOWN`` (``:118``) is never "safe to retry" (§15 line 358;
  AFG-INV-009).

Honest scope note (design #16 §3.4(b)): orthostate records carry **no** dedicated afg-bool
field — the seam is genuinely *coordinate*-dependent, not a produced-bool slot. afg
therefore owns the defining predicates (``no_blind_retry`` /
``cancel_ack_not_final_quantity_proof``) and consumes the orthostate **state** as input;
no phantom orthostate field is invented (the #10 phantom lesson, inverted).

Causal isolation: each assertion fixes a valid baseline and flips exactly one state token.

A test-only cross-import is **not** a runtime package edge (design #16 §3.4(d)/§7.1).
"""

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

# ---------------------------------------------------------------------------
# Token drift lock
# ---------------------------------------------------------------------------


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
    # No other member may be treated as a proof of non-acceptance by afg.
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


# ---------------------------------------------------------------------------
# no_blind_retry polarity (§14; AFG-INV-008)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# cancel-ACK polarity (§15; AFG-INV-009)
# ---------------------------------------------------------------------------


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
    """(§15:358 rationale) orthostate accepts a later valid fill after a local CANCELLED.

    The broker-order axis carries both ``CANCELLED`` and the fill states, and orthostate
    documents that a later valid fill is accepted even after a locally observed
    ``CANCELLED`` — so a cancel ACK can never be a Final Quantity Proof, and afg refuses
    every release / reuse / retry that rests on it alone.
    """
    assert BrokerOrderState.PARTIALLY_FILLED in set(BrokerOrderState)
    assert BrokerOrderState.FILLED in set(BrokerOrderState)
    for state in (BrokerOrderState.CANCELLED, BrokerOrderState.UNKNOWN):
        assert _cancel(state.value) is False
