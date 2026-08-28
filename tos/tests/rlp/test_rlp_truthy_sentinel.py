"""Truthy-sentinel structural seal — __bool__ raises + is-gate regression (design #25 §2.2/§4.2/§7).

``PlanResult`` / ``PromotionResult`` / ``TrialRunState`` / ``CoverageVerdict`` are non-empty
``StrEnum`` strings, so ``if result:`` / ``bool(state)`` would read a denial / non-permissive member
(``INELIGIBLE`` / ``HOLD`` / ``DENY`` / ``ABORTING`` / ``TERMINATED`` / ``UNCOVERED`` / ``UNKNOWN``)
as truthy — a catastrophic silent fail-open (the #13/#14 M1 lesson, adopted from the start). Each
subclasses ``_NonTruthyStrEnum`` (``__bool__`` raises). ``ScopeDimension`` / ``EvidenceClass`` are
plain closed StrEnums (structural membership tokens), deliberately NOT sealed.

Regime tag: vocabulary substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.rlp import (
    CoverageVerdict,
    EvidenceClass,
    PlanResult,
    PromotionResult,
    ScopeDimension,
    TrialRunState,
)

_RLP_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "rlp"

_SEALED_ENUMS = (PlanResult, PromotionResult, TrialRunState, CoverageVerdict)


def test_every_sealed_enum_member_raises_on_bool() -> None:
    """(§4.2 structural seal) bool(member) raises TypeError for EVERY member of each sealed enum."""
    for enum in _SEALED_ENUMS:
        for member in enum:
            with pytest.raises(TypeError):
                bool(member)


def test_denial_members_cannot_be_read_as_go() -> None:
    """(§4.2 — the catastrophic case) denial / non-permissive members are not truthy."""
    for member in (
        PlanResult.INELIGIBLE,
        PlanResult.HOLD,
        PromotionResult.DENY,
        PromotionResult.HOLD,
        TrialRunState.ABORTING,
        TrialRunState.TERMINATED,
        TrialRunState.INVALIDATED,
        CoverageVerdict.UNCOVERED,
        CoverageVerdict.UNKNOWN,
    ):
        with pytest.raises(TypeError):
            bool(member)


def test_is_identity_gate_still_works() -> None:
    """(the mandated gate) Explicit `is` identity comparison is unaffected by the seal."""
    assert (
        PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION
        is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION
    ) is True
    assert (
        PlanResult.INELIGIBLE is PlanResult.ELIGIBLE_TO_REQUEST_LIVE_AUTHORIZATION
    ) is False
    assert (
        PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE
        is PromotionResult.ELIGIBLE_TO_REQUEST_NEW_SCOPE
    ) is True
    assert (CoverageVerdict.COVERED is CoverageVerdict.COVERED) is True
    # …and set membership / .value / hashing (none call __bool__).
    assert PlanResult.INELIGIBLE in {PlanResult.INELIGIBLE}
    assert PlanResult.INELIGIBLE.value == "INELIGIBLE"
    assert hash(TrialRunState.RUNNING) == hash(TrialRunState.RUNNING)


def test_structural_enums_are_not_sealed() -> None:
    """(§2.2) ScopeDimension / EvidenceClass are plain closed membership tokens — truthiness is fine."""
    assert (
        bool(ScopeDimension.ENVIRONMENT) is True
    )  # a membership token, never a gate result
    assert bool(EvidenceClass.NEGATIVE_RESULTS) is True


def test_denial_values_would_have_failed_open_under_bare_truthiness() -> None:
    """(the trap itself) The denial .value strings are non-empty (would be truthy)."""
    assert bool(str(PlanResult.INELIGIBLE.value)) is True
    assert bool(str(PromotionResult.DENY.value)) is True
    assert bool(str(TrialRunState.TERMINATED.value)) is True
    assert bool(str(CoverageVerdict.UNCOVERED.value)) is True


def _bare_truthiness_offenders(path: Path) -> list[str]:
    """Return ``if <name>:`` / ``if not <name>:`` uses of a verdict-shaped local (AST)."""
    suspicious = {"result", "verdict", "state", "plan_result", "promotion_result"}
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            test = test.operand
        if isinstance(test, ast.Name) and test.id in suspicious:
            offenders.append(f"{path.name}:{node.lineno} bare truthiness on {test.id}")
    return offenders


def test_no_rlp_source_uses_bare_truthiness_on_a_verdict() -> None:
    """(source seal) No rlp module tests a verdict-shaped value for bare truthiness."""
    sources = sorted(_RLP_SRC.rglob("*.py"))
    assert sources, f"no tos.rlp source files found under {_RLP_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_bare_truthiness_offenders(path))
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"


def test_bare_truthiness_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The AST scan actually catches a planted ``if result:`` (not vacuous)."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(result):\n    if result:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    assert _bare_truthiness_offenders(planted) != []
