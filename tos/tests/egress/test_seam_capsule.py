"""MANDATED test-only seam cross-check: capsule Bindings chain terminus -> egress (design #22 §3.4/§3.5/§7)."""

from __future__ import annotations

import tos.egress as egress
from tos.capsule.capsule import Bindings
from tos.egress import QuorumCommitCertificate, exact_binding_holds

from ._egress_strategies import clean_authorized_coordinates, clean_qcc, clean_request


def test_capsule_bindings_carries_egress_request_digest_terminus() -> None:
    """(§3.4 capsule capsule.py:167) capsule Bindings owns the egress_request_digest chain terminus."""
    assert "egress_request_digest" in Bindings.model_fields
    bindings = Bindings(egress_request_digest="bytes-digest")
    assert bindings.egress_request_digest == "bytes-digest"


def test_egress_verifies_terminal_equivalence_to_the_capsule_terminus() -> None:
    """(§5.7 (ii) / §0.4e) exact_binding_holds admits only when request bytes == the capsule terminus."""
    request, qcc, authorized = (
        clean_request(),
        clean_qcc(),
        clean_authorized_coordinates(),
    )
    bindings = Bindings(egress_request_digest="bytes-digest")
    assert (
        exact_binding_holds(
            request, qcc, authorized, "CONFORMANT", bindings.egress_request_digest
        )
        is True
    )
    assert (
        exact_binding_holds(request, qcc, authorized, "CONFORMANT", "OTHER-terminus")
        is False
    )


def test_egress_qcc_carries_capsule_decision_digest_as_bound_claim() -> None:
    """(§2.4) The QCC decision_context_capsule_digest slot carries the injected capsule digest."""
    qcc = clean_qcc(decision_context_capsule_digest="dcc-digest")
    assert qcc.decision_context_capsule_digest == "dcc-digest"


def test_egress_carries_currentness_proof_id_but_does_not_own_currentness() -> None:
    """(§0.4f) EGRESS carries only the currentness-proof id claim — venue/iap/capsule own the predicate."""
    qcc = clean_qcc(egress_currentness_proof_id="ecp-1")
    assert qcc.egress_currentness_proof_id == "ecp-1"
    assert "egress_currentness_proof_id" in QuorumCommitCertificate.model_fields
    for name in (
        "egress_currentness_active",
        "active_egress_currentness",
        "egress_currentness_ok",
    ):
        assert not hasattr(egress, name)


def test_egress_reauthors_no_capsule_bindings() -> None:
    """(§3.5) egress re-authors NO capsule Bindings (forward-reference vs terminal-validation)."""
    assert not hasattr(egress, "Bindings")
    assert Bindings.__name__ == "Bindings"
