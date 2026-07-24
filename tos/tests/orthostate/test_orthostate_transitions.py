"""Per-dimension transition legality — arrow tables + positive-proof guards (§6; §5/§6/§8).

Only the exact ADR §5 / §6 / §8 arrows are allowed; PROPOSED -> DENIED is NOT (DENIED
branches from APPROVED); CLOSED / WITHDRAWN entry needs the no-potentially-live proof;
SEND_FAILED_PROVEN is unreachable via timeout / absence (positive evidence only);
RECONCILED is unreachable without corroboration + FQP; terminals have no outgoing arrow;
None on either side fails closed. Broker Order is a state set (no arrow predicate).
[STATE-EV-003 slice, per-dimension direction substrate]
"""

from __future__ import annotations

import pytest
from tos.orthostate import (
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
    attempt_transition_allowed,
    intent_transition_allowed,
    knowledge_transition_allowed,
)
from tos.orthostate.predicates import (
    _ATTEMPT_TRANSITIONS,
    _INTENT_TRANSITIONS,
    _KNOWLEDGE_TRANSITIONS,
)

_I = IntentState
_A = TransmissionAttemptState
_K = KnowledgeState


# ---------------------------------------------------------------------------
# Intent (ADR §5) — DENIED branch, proof-gated terminals, non-outgoing terminals
# ---------------------------------------------------------------------------


def test_intent_proposed_to_denied_not_allowed() -> None:
    """(canary §2.2 regression-lock) PROPOSED -> DENIED is NOT allowed (DENIED branches APPROVED)."""
    assert intent_transition_allowed(_I.PROPOSED, _I.DENIED) is False


def test_intent_approved_to_denied_allowed() -> None:
    """(guard True) APPROVED -> DENIED is allowed (the §5 line 71 branch)."""
    assert intent_transition_allowed(_I.APPROVED, _I.DENIED) is True


def test_intent_forward_progression_allowed() -> None:
    """(guard True) The core PROPOSED -> APPROVED -> AUTHORIZED_FOR_CAPACITY -> ACTIVE arrows."""
    assert intent_transition_allowed(_I.PROPOSED, _I.APPROVED) is True
    assert intent_transition_allowed(_I.APPROVED, _I.AUTHORIZED_FOR_CAPACITY) is True
    assert intent_transition_allowed(_I.AUTHORIZED_FOR_CAPACITY, _I.ACTIVE) is True


@pytest.mark.parametrize("terminal_to", [_I.CLOSED, _I.WITHDRAWN])
def test_intent_closed_withdrawn_require_proof(terminal_to: IntentState) -> None:
    """(canary §5 line 77) CLOSED / WITHDRAWN entry requires no-potentially-live proof True."""
    assert intent_transition_allowed(_I.ACTIVE, terminal_to) is False  # None => reject
    assert (
        intent_transition_allowed(
            _I.ACTIVE, terminal_to, no_potentially_live_proof=False
        )
        is False
    )
    assert (
        intent_transition_allowed(
            _I.ACTIVE, terminal_to, no_potentially_live_proof=True
        )
        is True
    )


@pytest.mark.parametrize("terminal", [_I.CLOSED, _I.DENIED, _I.WITHDRAWN])
def test_intent_terminals_have_no_outgoing(terminal: IntentState) -> None:
    """(canary) A terminal Intent state has no outgoing transition (with proof supplied too)."""
    for to_state in _I:
        assert (
            intent_transition_allowed(
                terminal, to_state, no_potentially_live_proof=True
            )
            is False
        )


def test_intent_none_either_side_rejected() -> None:
    """(canary) None on either side fails closed."""
    assert intent_transition_allowed(None, _I.APPROVED) is False
    assert intent_transition_allowed(_I.PROPOSED, None) is False


# ---------------------------------------------------------------------------
# Transmission Attempt (ADR §6) — SEND_FAILED_PROVEN needs positive evidence
# ---------------------------------------------------------------------------


def test_attempt_chain_allowed() -> None:
    """(guard True) The NONE -> ... -> SENT_UNCONFIRMED chain arrows are allowed."""
    assert attempt_transition_allowed(_A.NONE, _A.PREPARED) is True
    assert attempt_transition_allowed(_A.PREPARED, _A.CAPABILITY_ISSUED) is True
    assert attempt_transition_allowed(_A.CAPABILITY_ISSUED, _A.SEND_STARTED) is True
    assert attempt_transition_allowed(_A.SEND_STARTED, _A.SENT_UNCONFIRMED) is True
    assert attempt_transition_allowed(_A.SENT_UNCONFIRMED, _A.ACK_OBSERVED) is True
    assert attempt_transition_allowed(_A.SENT_UNCONFIRMED, _A.SUPERSEDED) is True


def test_send_failed_proven_unreachable_without_positive_evidence() -> None:
    """(canary §6 line 97) SEND_FAILED_PROVEN is unreachable via timeout / absence (None/False)."""
    assert (
        attempt_transition_allowed(_A.SENT_UNCONFIRMED, _A.SEND_FAILED_PROVEN) is False
    )
    assert (
        attempt_transition_allowed(
            _A.SENT_UNCONFIRMED,
            _A.SEND_FAILED_PROVEN,
            positive_send_failure_evidence=False,
        )
        is False
    )


def test_send_failed_proven_reachable_with_positive_evidence() -> None:
    """(guard True) SEND_FAILED_PROVEN is reachable only with positive evidence."""
    assert (
        attempt_transition_allowed(
            _A.SENT_UNCONFIRMED,
            _A.SEND_FAILED_PROVEN,
            positive_send_failure_evidence=True,
        )
        is True
    )


def test_attempt_none_either_side_rejected() -> None:
    """(canary) None on either side fails closed."""
    assert attempt_transition_allowed(None, _A.PREPARED) is False
    assert attempt_transition_allowed(_A.SEND_STARTED, None) is False


def test_attempt_backward_transition_rejected() -> None:
    """(canary) A backward attempt transition is not a §6 arrow."""
    assert attempt_transition_allowed(_A.SEND_STARTED, _A.PREPARED) is False


# ---------------------------------------------------------------------------
# Knowledge (ADR §8) — RECONCILED needs corroboration + FQP; STALE / quarantine-exit
# ---------------------------------------------------------------------------


def test_knowledge_reconciled_unreachable_without_corroboration() -> None:
    """(canary §8 line 140) RECONCILED needs corroboration AND FQP-where-broker; None => reject."""
    assert knowledge_transition_allowed(_K.RECONCILING, _K.RECONCILED) is False
    assert (
        knowledge_transition_allowed(
            _K.RECONCILING,
            _K.RECONCILED,
            corroboration=True,
            final_quantity_proof_where_broker_involved=None,
        )
        is False
    )
    assert (
        knowledge_transition_allowed(
            _K.RECONCILING,
            _K.RECONCILED,
            corroboration=None,
            final_quantity_proof_where_broker_involved=True,
        )
        is False
    )


def test_knowledge_reconciled_reachable_with_both_proofs() -> None:
    """(guard True) RECONCILED is reachable with corroboration AND FQP both True."""
    assert (
        knowledge_transition_allowed(
            _K.RECONCILING,
            _K.RECONCILED,
            corroboration=True,
            final_quantity_proof_where_broker_involved=True,
        )
        is True
    )


def test_knowledge_stale_needs_freshness_lost() -> None:
    """(canary §8 line 141) STALE entry requires freshness_lost True."""
    assert knowledge_transition_allowed(_K.CONSISTENT, _K.STALE) is False
    assert (
        knowledge_transition_allowed(_K.CONSISTENT, _K.STALE, freshness_lost=True)
        is True
    )


def test_knowledge_quarantine_exit_needs_evidence() -> None:
    """(canary §8 line 142) Exiting QUARANTINED requires quarantine_exit_evidence True."""
    assert knowledge_transition_allowed(_K.QUARANTINED, _K.RECONCILING) is False
    assert (
        knowledge_transition_allowed(
            _K.QUARANTINED, _K.RECONCILING, quarantine_exit_evidence=True
        )
        is True
    )


def test_knowledge_reopen_reconciled_to_conflicted_allowed() -> None:
    """(§11 line 177) A fresh conflict re-opening RECONCILED -> CONFLICTED is allowed (increase)."""
    assert knowledge_transition_allowed(_K.RECONCILED, _K.CONFLICTED) is True


def test_knowledge_none_either_side_rejected() -> None:
    """(canary) None on either side fails closed."""
    assert knowledge_transition_allowed(None, _K.CONSISTENT) is False
    assert knowledge_transition_allowed(_K.CONFLICTED, None) is False


# ---------------------------------------------------------------------------
# Exhaustive arrow-table sweeps (neither too permissive nor too restrictive)
# ---------------------------------------------------------------------------


def test_intent_sweep_matches_arrow_table() -> None:
    """(exhaustive) Every Intent pair is allowed (proof supplied) iff it is a §5 arrow."""
    for frm in _I:
        for to in _I:
            expected = (frm, to) in _INTENT_TRANSITIONS
            got = intent_transition_allowed(frm, to, no_potentially_live_proof=True)
            assert got is expected, f"({frm}, {to})"


def test_attempt_sweep_matches_arrow_table() -> None:
    """(exhaustive) Every Attempt pair is allowed (evidence supplied) iff it is a §6 arrow."""
    for frm in _A:
        for to in _A:
            expected = (frm, to) in _ATTEMPT_TRANSITIONS
            got = attempt_transition_allowed(
                frm, to, positive_send_failure_evidence=True
            )
            assert got is expected, f"({frm}, {to})"


def test_knowledge_sweep_matches_arrow_table() -> None:
    """(exhaustive) Every Knowledge pair is allowed (all proofs supplied) iff it is a §8 arrow."""
    for frm in _K:
        for to in _K:
            expected = (frm, to) in _KNOWLEDGE_TRANSITIONS
            got = knowledge_transition_allowed(
                frm,
                to,
                corroboration=True,
                final_quantity_proof_where_broker_involved=True,
                freshness_lost=True,
                quarantine_exit_evidence=True,
            )
            assert got is expected, f"({frm}, {to})"
