"""Final Quantity Proof recipe (design #10 §6.3; BC-EV-007; §15.2/§15.3/§15.4).

Each of the 7 §15.3 prohibited proofs, alone, => not adequate; a complete §15.2 proof with a
§15.4 terminal marker => adequate. This bool is the recon ``final_quantity_proof_token`` /
orthostate FQP producer.
"""

from __future__ import annotations

import pytest
from tos.brokercap import (
    FinalQuantityEvidence,
    FinalQuantityProofRule,
    ProhibitedProof,
    fqp_adequate,
)

from ._brokercap_strategies import complete_fqp_evidence, fqp_rule

# ---------------------------------------------------------------------------
# Positive side
# ---------------------------------------------------------------------------


def test_complete_proof_is_adequate() -> None:
    """(§15.2 canary b) All conjuncts True + §15.4 terminal marker + no prohibited sole basis => True."""
    assert fqp_adequate(fqp_rule(), complete_fqp_evidence()) is True


def test_late_event_window_alternative_terminal_marker() -> None:
    """(§15.4) The bounded-correction-window marker alone also satisfies the terminal requirement."""
    rule = fqp_rule(no_later_change_asserted=None, late_event_window_defined=True)
    assert fqp_adequate(rule, complete_fqp_evidence()) is True


# ---------------------------------------------------------------------------
# §15.3 prohibited proofs — each alone => not adequate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("proof", list(ProhibitedProof), ids=lambda p: p.value)
def test_each_prohibited_proof_alone_is_inadequate(proof: ProhibitedProof) -> None:
    """(§15.3 verbatim) Any of the 7 prohibited proofs as the sole basis => not adequate."""
    # Even with every positive conjunct set, a sole prohibited basis fails closed.
    evidence = complete_fqp_evidence(sole_prohibited_basis=proof)
    assert fqp_adequate(fqp_rule(), evidence) is False


def test_all_seven_prohibited_proofs_covered() -> None:
    """(§15.3) The parametrization exercises exactly the 7 prohibited proofs."""
    assert len(list(ProhibitedProof)) == 7


# ---------------------------------------------------------------------------
# §15.2 required conjuncts — each missing => not adequate (drop-one)
# ---------------------------------------------------------------------------

_CONJUNCTS = (
    "broker_order_identity_or_bounded_effect",
    "final_cumulative_filled_quantity",
    "zero_remaining_executable_quantity",
    "corrections_busts_late_events_handled",
    "evidence_source_provenance",
    "within_valid_window",
    "ordering_waiting_rule_satisfied",
)


@pytest.mark.parametrize("conjunct", _CONJUNCTS)
def test_missing_required_conjunct_is_inadequate(conjunct: str) -> None:
    """(§15.2 drop-one) Dropping any required conjunct (None) => not adequate."""
    evidence = complete_fqp_evidence(**{conjunct: None})
    assert fqp_adequate(fqp_rule(), evidence) is False


@pytest.mark.parametrize("conjunct", _CONJUNCTS)
def test_false_required_conjunct_is_inadequate(conjunct: str) -> None:
    """(§15.2) A required conjunct explicitly False => not adequate."""
    evidence = complete_fqp_evidence(**{conjunct: False})
    assert fqp_adequate(fqp_rule(), evidence) is False


# ---------------------------------------------------------------------------
# §15.4 terminal event required
# ---------------------------------------------------------------------------


def test_no_terminal_marker_is_inadequate() -> None:
    """(§15.4) Neither no-later-change nor late-event-window defined => inadequate (unspecified)."""
    rule = FinalQuantityProofRule(
        order_type="LIMIT",
        prohibited_proofs=frozenset(ProhibitedProof),
        no_later_change_asserted=None,
        late_event_window_defined=None,
    )
    assert fqp_adequate(rule, complete_fqp_evidence()) is False


def test_empty_evidence_is_inadequate() -> None:
    """(§6.3) A wholly empty evidence bundle => not adequate (all conjuncts None)."""
    assert fqp_adequate(fqp_rule(), FinalQuantityEvidence()) is False
