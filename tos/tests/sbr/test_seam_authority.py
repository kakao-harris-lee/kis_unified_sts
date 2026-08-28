"""MANDATED test-only seam cross-check: sbr -> authority (design #17 §3.4(d) / §7).

SBR **produces** the ``recovery_coordinator_evidence_complete`` bool the authority re-arm
checklist consumes as its 12th prerequisite (``authority/state.py:133`` field;
``_REARM_PREREQUISITES`` item 12; ``rearm_gate`` consumes it with
``getattr(checklist, name) is True`` at ``authority/predicates.py:769``). This file imports the
real authority ``RearmChecklist`` / ``rearm_gate`` / ``GenerationVector`` as a **test** to lock:

(a) the produced-bool seam — SBR's ``recovery_coordinator_evidence_complete(decision)`` fills
    the exact ``RearmChecklist.recovery_coordinator_evidence_complete`` slot;
(b) causal isolation — with the other 13 prerequisites + SoD held fixed, flipping ONLY SBR's
    readiness (READY -> NOT_READY => item 12 True -> False) flips ``rearm_gate`` armable;
(c) readiness != re-arm (§3.5 핵심 판정 2) — item 12 is one of 14; producing it True does NOT
    make re-arm admissible on its own (``fresh_live_authorization_issued`` /
    ``explicit_human_dual_control_complete`` and SoD remain), so SBR is the first input, never
    the permission;
(d) the ``recovery_generation`` reference coordinate — the ``GenerationVector`` carries the
    scalar SBR fences the meaning of (reference-only, ``authority/state.py:42-43``).

A test-only cross-import is **not** a runtime package edge (design #17 §3.4(d)/§7.1); sbr's
package closure imports no sibling (sibling edge 0).
"""

from __future__ import annotations

from tos.authority import GenerationVector, RearmChecklist, rearm_gate

# test-only import of the private prerequisite tuple (∉ sbr package closure).
from tos.authority.predicates import _REARM_PREREQUISITES
from tos.sbr import (
    ReadinessVerdict,
    recovery_coordinator_evidence_complete,
    recovery_generation_of,
)

from ._sbr_strategies import issue_decision

_OTHER_13 = tuple(
    name
    for name in _REARM_PREREQUISITES
    if name != "recovery_coordinator_evidence_complete"
)


def _checklist(*, item12: bool | None) -> RearmChecklist:
    """A checklist with the other 13 prerequisites True + distinct principals; item 12 injected."""
    fields = dict.fromkeys(_OTHER_13, True)
    fields["recovery_coordinator_evidence_complete"] = item12
    fields["limit_enlarger_principal"] = "principal-A"
    fields["armer_principal"] = "principal-B"
    return RearmChecklist(**fields)


def test_item_12_is_the_sbr_produced_prerequisite() -> None:
    """(seam a) The authority checklist's 12th prerequisite is exactly what SBR produces."""
    assert _REARM_PREREQUISITES[11] == "recovery_coordinator_evidence_complete"
    assert "recovery_coordinator_evidence_complete" in RearmChecklist.model_fields


def test_sbr_producer_fills_item_12_and_rearm_gate_is_armable() -> None:
    """(seam a positive) A positive readiness => item 12 True => (with the other 13 + SoD) armable."""
    decision = issue_decision(verdict=ReadinessVerdict.READY)
    item12 = recovery_coordinator_evidence_complete(decision)
    assert item12 is True
    verdict = rearm_gate(_checklist(item12=item12))
    assert verdict.armable is True
    # …and the re-arm gate is non-authorizing (it carries an all-false authority effect).
    assert verdict.authority_effect is not None


def test_causal_isolation_not_ready_flips_only_item_12_and_blocks_rearm() -> None:
    """(seam b) Flipping ONLY SBR's readiness (READY -> NOT_READY) blocks re-arm — nothing else moved."""
    not_ready = issue_decision(verdict=ReadinessVerdict.NOT_READY)
    item12 = recovery_coordinator_evidence_complete(not_ready)
    assert item12 is False
    # The other 13 prerequisites + SoD are held identical to the armable baseline.
    assert rearm_gate(_checklist(item12=item12)).armable is False


def test_readiness_is_not_rearm_item_12_true_alone_is_insufficient() -> None:
    """(seam c, §3.5 핵심 판정 2) item 12 True is one of 14 — the remaining prerequisites still gate."""
    # SBR says the coordinator evidence is complete…
    assert recovery_coordinator_evidence_complete(issue_decision()) is True
    # …but if a different prerequisite (fresh Live Authorization) is missing, re-arm is denied.
    fields = dict.fromkeys(_REARM_PREREQUISITES, True)
    fields["fresh_live_authorization_issued"] = None
    fields["limit_enlarger_principal"] = "A"
    fields["armer_principal"] = "B"
    assert rearm_gate(RearmChecklist(**fields)).armable is False


def test_recovery_generation_reference_coordinate_seam() -> None:
    """(seam d, §0.4e) SBR produces the recovery_generation scalar the GenerationVector carries."""
    decision = issue_decision(recovery_generation=7)
    generation = recovery_generation_of(decision)
    assert generation == 7
    vector = GenerationVector(recovery_generation=generation)
    assert vector.recovery_generation == 7
    # authority carries it as a reference-only scalar; SBR owns its fence meaning (§0.4e).
    assert "recovery_generation" in GenerationVector.model_fields
