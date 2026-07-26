"""MANDATED test-only seam cross-check: rcl commit-proof / claim-to-send -> egress (design #22 §3.4/§3.5/§7).

rcl (ADR-002-002 / ADR-002-012) is the **upstream** Safety Commit Log: it owns the ADR-002-012
Commit Proof coordinates and the fenced single-use ``TransmissionCapability`` (``rcl/records.py:249``)
plus the ``claim_capability`` nonce ledger (``rcl/predicates.py:677`` — nonce single-use + replay,
``rcl/predicates.py:698-703``). EGRESS **consumes** those produced facts as injected scalars /
verdicts and **re-authors none** of them (sibling edge 0, §0.4b/§3.5): the QCC carries the rcl
commit-proof coordinates as bound claims, and ``capability_and_permit_single_use`` consumes injected
prior-claim observations. This file imports the real rcl models as a **test** to prove the seam
anchors exist and are the *producer* side; the import-closure test proves ``tos.rcl`` is **absent**
from the egress runtime closure.

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV-004/005 substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.egress as egress
from tos.egress import (
    ClaimObservation,
    capability_and_permit_single_use,
)
from tos.rcl.predicates import claim_capability
from tos.rcl.records import TransmissionCapability
from tos.rcl.state import ClaimOutcome


def test_rcl_owns_transmission_capability_scalar() -> None:
    """(§3.4 rcl records.py:249) rcl owns TransmissionCapability (nonce single-use) — egress consumes."""
    assert "nonce" in TransmissionCapability.model_fields
    assert "single_use" in TransmissionCapability.model_fields


def test_rcl_owns_claim_capability_nonce_ledger() -> None:
    """(§3.4 rcl predicates.py:677) rcl owns claim_capability — nonce single-use + replay verdict."""
    first = claim_capability("nonce-1", [])
    assert isinstance(first, ClaimOutcome)
    assert first.consumed_now is True and first.replay is False


def test_egress_reauthors_no_rcl_claim_ledger() -> None:
    """(§3.5) egress re-authors NO rcl claim_capability / TransmissionCapability / writer_fenced."""
    assert not hasattr(egress, "claim_capability")
    assert not hasattr(egress, "TransmissionCapability")
    assert not hasattr(egress, "writer_fenced")
    assert not hasattr(egress, "ClaimOutcome")


def test_egress_claim_observation_is_a_distinct_local_consumer_model() -> None:
    """(§3.5) egress ClaimObservation is a distinct local model consuming injected prior claims.

    It is NOT the rcl ``ClaimOutcome`` / ``ClaimRecord``: egress adds only the principal + request
    binding on top of the injected nonce ledger rcl already owns (§5.6). A prior claim of a nonce
    (from the injected rcl-produced ledger) makes a fresh claim not single-use.
    """
    assert ClaimObservation is not ClaimOutcome
    # egress consumes the injected prior claim: a re-used nonce is rejected (single-use, §5.6).
    prior = [ClaimObservation(nonce="cap-1", principal="p-1", request_digest="rq-1")]
    assert (
        capability_and_permit_single_use(
            "cap-1", "afp-1", prior, principal="p-1", request_digest="rq-1"
        )
        is False
    )
    # …and a fresh nonce with no prior claim passes (the producer/consumer seam works).
    assert (
        capability_and_permit_single_use(
            "cap-1", "afp-1", [], principal="p-1", request_digest="rq-1"
        )
        is True
    )
