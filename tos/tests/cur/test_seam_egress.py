"""MANDATED test-only seam cross-check: egress latch + QCC currentness-proof id -> cur (design #23 §3.5/§7)."""

from __future__ import annotations

import tos.cur as cur
from tos.cur import EgressProofCoordinateSet, proof_admissible
from tos.egress import QuorumCommitCertificate, RestrictiveLatchState
from tos.egress.predicates import monotonic_denial_no_revival

from ._cur_strategies import clean_coordinates, clean_proof


def test_egress_owns_the_latch_state_machine_and_resolver() -> None:
    """(§3.5 egress predicates.py:519) egress owns monotonic_denial_no_revival — cur re-authors none."""
    assert monotonic_denial_no_revival(None, []) is RestrictiveLatchState.DENY_LATCHED
    assert (
        monotonic_denial_no_revival(RestrictiveLatchState.DENY_LATCHED, [])
        is RestrictiveLatchState.DENY_LATCHED
    )
    assert (
        monotonic_denial_no_revival(RestrictiveLatchState.CLEAR, [])
        is RestrictiveLatchState.CLEAR
    )


def test_cur_reauthors_no_latch_state_machine() -> None:
    """(§0.4d) cur re-authors NO RestrictiveLatchState / monotonic_denial_no_revival."""
    assert not hasattr(cur, "RestrictiveLatchState")
    assert not hasattr(cur, "monotonic_denial_no_revival")


def test_cur_consumes_the_egress_latch_as_injected_local_latch_clear() -> None:
    """(§5.7 / §0.4d) cur consumes the egress-resolved latch as an injected local_latch_clear bool."""
    resolved_clear = monotonic_denial_no_revival(RestrictiveLatchState.CLEAR, [])
    resolved_deny = monotonic_denial_no_revival(None, [])
    clear_injection = resolved_clear is RestrictiveLatchState.CLEAR
    deny_injection = resolved_deny is RestrictiveLatchState.CLEAR
    assert (
        proof_admissible(
            clean_proof(
                coordinates=clean_coordinates(local_latch_clear=clear_injection)
            )
        )
        is True
    )
    assert (
        proof_admissible(
            clean_proof(coordinates=clean_coordinates(local_latch_clear=deny_injection))
        )
        is False
    )


def test_cur_local_latch_clear_is_positive_polarity() -> None:
    """(§5.7) The injected local_latch_clear is positive-polarity — only True is CLEAR."""
    coords = EgressProofCoordinateSet(local_latch_clear=True)
    assert coords.local_latch_clear is True
    assert (
        proof_admissible(
            clean_proof(coordinates=clean_coordinates(local_latch_clear=None))
        )
        is False
    )


def test_egress_qcc_carries_the_currentness_proof_id_claim() -> None:
    """(§0.4c egress records.py:141/189) The egress QCC carries egress_currentness_proof_id (cur → egress)."""
    assert "egress_currentness_proof_id" in QuorumCommitCertificate.model_fields
    qcc = QuorumCommitCertificate(egress_currentness_proof_id="ecp-1")
    assert qcc.egress_currentness_proof_id == "ecp-1"
    assert not hasattr(cur, "QuorumCommitCertificate")
