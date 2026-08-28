"""MANDATED test-only seam cross-check: capsule Bindings chain terminus -> egress (design #22 §3.4/§3.5/§7).

capsule (ADR-002-018) owns the downstream ``Bindings`` chain, whose ``egress_request_digest``
(``capsule/capsule.py:167``) is the **chain terminus** — a forward reference that stays ``None`` in
Phase 1 (capsule → egress declaration direction). EGRESS verifies the **terminal** equivalence: the
actual outbound request's bytes digest must equal that injected capsule terminus
(``exact_binding_holds`` (ii), §0.4e). The two are different directions (forward-reference vs
terminal-validation), so EGRESS **re-authors none** of the capsule ``Bindings`` (sibling edge 0).
The venue / iap / capsule per-decision egress-currentness predicates are each sibling-owned; EGRESS
consumes only the QCC currentness-proof id as a structural claim (§0.4f — CUR complete-vector is
injected). This file imports the real capsule model as a **test**; the import-closure test proves
``tos.capsule`` is **absent** from the egress runtime closure.

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV-005 substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.egress as egress
from tos.capsule.capsule import Bindings
from tos.egress import QuorumCommitCertificate, exact_binding_holds

from ._egress_strategies import clean_authorized_coordinates, clean_qcc, clean_request


def test_capsule_bindings_carries_egress_request_digest_terminus() -> None:
    """(§3.4 capsule capsule.py:167) capsule Bindings owns the egress_request_digest chain terminus."""
    assert "egress_request_digest" in Bindings.model_fields
    # capsule is the forward-reference producer of the terminus (None in Phase 1 by default).
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
    # Terminal equivalence: the injected capsule terminus equals the request bytes digest.
    assert (
        exact_binding_holds(
            request, qcc, authorized, "CONFORMANT", bindings.egress_request_digest
        )
        is True
    )
    # A different capsule terminus (substitution) is denied.
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
    # EGRESS structurally carries the single-use currentness-proof id (CUR/venue/iap owned upstream,
    # injected); it authors no egress-currentness predicate of its own.
    qcc = clean_qcc(egress_currentness_proof_id="ecp-1")
    assert qcc.egress_currentness_proof_id == "ecp-1"
    assert "egress_currentness_proof_id" in QuorumCommitCertificate.model_fields
    # egress does NOT re-author venue/iap/capsule egress-currentness predicates.
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
