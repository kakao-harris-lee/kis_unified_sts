"""MANDATED test-only seam cross-check: evidence SegmentCommitmentScheme + causal-chain ↔ rlp (§3.5/§0.4d).

evidence (ADR-002-016) owns the trial evidence **assembly + custody integrity** — the
``SegmentCommitmentScheme`` (``evidence/ledger.py``) and ``causal_chain_complete``
(``evidence/predicates.py``) + the gap machine. rlp owns the trial-package **completeness contract**
(§16 element-class manifest + negative-result retention gate) and **consumes** the evidence
``causal_chain_complete`` / gap-status as **injected verdicts** — a **2-gate separation** (§0.4d): the
evidence causal-chain gate and the rlp completeness gate are different axes. This file imports the real
evidence symbols as a **test**; the import-closure test proves ``tos.evidence`` is **absent** from the
rlp runtime closure.

Regime tag: structural / completeness predicate substrate only; RLP-EV-005 substrate; EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import tos.rlp as rlp
from tos.evidence import SegmentCommitmentScheme, causal_chain_complete
from tos.rlp import (
    MANDATED_EVIDENCE_FLOOR,
    TrialEvidencePackage,
    evidence_package_complete,
)

from ._rlp_strategies import clean_package, clean_policy


def test_evidence_owns_assembly_and_causal_chain() -> None:
    """(§0.4d) The SegmentCommitmentScheme + causal_chain_complete live in evidence, not rlp."""
    assert SegmentCommitmentScheme is not None
    assert callable(causal_chain_complete)


def test_rlp_reauthors_no_evidence_assembly_or_causal_chain() -> None:
    """(§0.4d / §3.4) rlp re-authors NO SegmentCommitmentScheme / causal_chain_complete."""
    assert not hasattr(rlp, "SegmentCommitmentScheme")
    assert not hasattr(rlp, "causal_chain_complete")


def test_two_gate_separation_causal_chain_is_injected() -> None:
    """(§0.4d 2-gate) The evidence causal-chain gate is injected; the rlp completeness gate is separate.

    A package that is manifest-complete + negatives-retained + selection-fixed but whose **injected**
    ``causal_chain_complete`` is not True fails the rlp gate — proving rlp consumes (never re-authors)
    the evidence verdict, and the two gates are distinct axes.
    """
    incomplete_chain = clean_package(causal_chain_complete=None)
    assert (
        evidence_package_complete(
            incomplete_chain, clean_policy(), MANDATED_EVIDENCE_FLOOR
        )
        is False
    )
    unresolved_gap = clean_package(has_unresolved_gap=True)
    assert (
        evidence_package_complete(
            unresolved_gap, clean_policy(), MANDATED_EVIDENCE_FLOOR
        )
        is False
    )
    # the injected integrity verdicts are fields, not re-derived by rlp.
    assert "causal_chain_complete" in TrialEvidencePackage.model_fields
    assert "has_unresolved_gap" in TrialEvidencePackage.model_fields
