"""Seam: ``tos.posttrade`` <-> ``tos.cur`` — post-trade currentness is already owned.

cur (ADR-002-024, committed after this design's v1.0 was authored) already owns a
**post-trade** currentness dimension: ``DimensionKey.POST_TRADE``. It also owns the proof
result (``CURRENT`` / ``RESTRICTED`` / ``UNKNOWN``) and the admission (``ADMIT`` / ``DENY``).

So the §22 division is unambiguous (design #24 §3.5, the §22 row / §6.5): cur owns the
currentness **vector**, the active-generation **fence**, and the **admission**; this package
supplies only the §8.1 identity coordinates — the post-trade finality policy id / generation /
digest, the active obligation-set id / digest, the obligation generation, and the statement
coverage manifest id / digest. All eight of those VP-002 slots are ``TBD`` / ``null``, so no
value is hardcoded here either.

The fencing runtime itself is PTF-EV-010 ``EV-L2/3+Broker+Security`` and is **not** authored:
this package has no currentness predicate at all.

Locks **2** of the 19 injected tokens: ``DimensionKey.POST_TRADE``,
``CurrentnessAdmission.ADMIT``. Test-only sibling imports are not runtime package edges.
"""

from __future__ import annotations

import tos.posttrade.predicates as posttrade_predicates
from tos.posttrade import (
    CURRENTNESS_ADMISSION_ADMIT,
    CURRENTNESS_DIMENSION_POST_TRADE,
    EconomicObligationRecord,
    PostTradeFinalityProof,
    StatementCoverageManifest,
    finality_proof_current,
)

from ._posttrade_strategies import clean_finality_proof


def test_currentness_dimension_token_drift_lock() -> None:
    """(token 18 of 19) cur ``DimensionKey.POST_TRADE`` — cur owns this dimension."""
    from tos.cur import DimensionKey

    assert DimensionKey.POST_TRADE.value == CURRENTNESS_DIMENSION_POST_TRADE


def test_currentness_admission_token_drift_lock() -> None:
    """(token 19 of 19) cur ``CurrentnessAdmission.ADMIT``."""
    from tos.cur import CurrentnessAdmission

    assert CurrentnessAdmission.ADMIT.value == CURRENTNESS_ADMISSION_ADMIT


def test_cur_owns_the_three_way_proof_result_this_package_never_produces() -> None:
    """(§3.5 §22 row) ``CURRENT`` / ``RESTRICTED`` / ``UNKNOWN`` is cur's verdict space."""
    from tos.cur import ProofResult

    assert {member.value for member in ProofResult} == {
        "CURRENT",
        "RESTRICTED",
        "UNKNOWN",
    }


def test_this_package_authors_no_currentness_fence() -> None:
    """(§6.5) The fencing runtime is PTF-EV-010 ``EV-L2/3+Security`` — deferred, not built."""
    for forbidden in (
        "currentness_vector",
        "currentness_proof",
        "generation_fence",
        "active_generation_current",
        "fence_stale_writer",
        "currentness_admission",
    ):
        assert not hasattr(posttrade_predicates, forbidden)


def test_the_one_generation_comparison_here_is_the_reopen_rule_not_a_fence() -> None:
    """(§5.7 M2 vs §22) ``finality_proof_current`` is a **proof** rule, not a fence.

    It answers "is this proof still the current one for its obligation?" (§11 line 330, the
    correction reopen). It does not admit or deny anything, consults no currentness vector,
    and reads no clock — cur owns all of that.
    """
    proof = clean_finality_proof(bound_generation=1)
    assert finality_proof_current(proof, 1) is True
    assert finality_proof_current(proof, 2) is False
    assert finality_proof_current.__doc__ is not None
    assert "ordering" in finality_proof_current.__doc__


def test_the_identity_coordinates_this_package_supplies_are_carried_not_judged() -> (
    None
):
    """(§8.1) The three §22 identity families exist as **fields**, with no verdict attached.

    All eight VP-002 currentness slots are ``TBD`` / ``null``, so Phase 1 carries the
    coordinates and cur decides.
    """
    assert "obligation_generation" in EconomicObligationRecord.model_fields
    assert "bound_generation" in PostTradeFinalityProof.model_fields
    assert "manifest_generation" in StatementCoverageManifest.model_fields
    # ... and none of them is accompanied by a currentness verdict field
    for model in (
        EconomicObligationRecord,
        PostTradeFinalityProof,
        StatementCoverageManifest,
    ):
        fields = set(model.model_fields)
        for forbidden in ("currentness", "is_current", "admission", "proof_result"):
            assert forbidden not in fields


def test_no_currentness_bound_is_hardcoded() -> None:
    """(§8.1) The generation comparison is pure integer equality — no age, no threshold."""
    proof = clean_finality_proof(bound_generation=99)
    assert finality_proof_current(proof, 99) is True
    assert finality_proof_current(proof, 98) is False
    assert finality_proof_current(proof, 100) is False
