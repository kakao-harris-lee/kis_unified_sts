"""Truthy-sentinel structural seal — __bool__ raises + is-gate regression (design #23 §2.2/§4.2/§7).

``ProofResult`` (CURRENT / RESTRICTED / UNKNOWN) and ``CurrentnessAdmission`` (ADMIT / DENY) are
non-empty ``StrEnum`` strings, so ``if result:`` / ``bool(admission)`` would read a **denial** member
(RESTRICTED / UNKNOWN / DENY) as truthy — a catastrophic silent fail-open (the #13/#14 M1 lesson,
adopted from the start). Each subclasses ``_NonTruthyStrEnum`` (``__bool__`` raises). ``DimensionKey``
is a plain closed StrEnum (structural membership token), deliberately NOT sealed.

Regime tag: vocabulary substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.cur import CurrentnessAdmission, DimensionKey, ProofResult

_CUR_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "cur"

_SEALED_ENUMS = (ProofResult, CurrentnessAdmission)


def test_every_sealed_enum_member_raises_on_bool() -> None:
    """(§4.2 structural seal) bool(member) raises TypeError for EVERY member of each sealed enum."""
    for enum in _SEALED_ENUMS:
        for member in enum:
            with pytest.raises(TypeError):
                bool(member)


def test_denial_members_cannot_be_read_as_conformance() -> None:
    """(§4.2 — the catastrophic case) RESTRICTED / UNKNOWN / DENY are not truthy."""
    for member in (
        ProofResult.RESTRICTED,
        ProofResult.UNKNOWN,
        CurrentnessAdmission.DENY,
    ):
        with pytest.raises(TypeError):
            bool(member)


def test_is_identity_gate_still_works() -> None:
    """(the mandated gate) Explicit `is` identity comparison is unaffected by the seal."""
    assert (ProofResult.CURRENT is ProofResult.CURRENT) is True
    assert (ProofResult.RESTRICTED is ProofResult.CURRENT) is False
    assert (CurrentnessAdmission.ADMIT is CurrentnessAdmission.ADMIT) is True
    # …and set membership / .value / hashing (none call __bool__).
    assert ProofResult.CURRENT in {ProofResult.CURRENT}
    assert ProofResult.CURRENT.value == "CURRENT"
    assert hash(ProofResult.UNKNOWN) == hash(ProofResult.UNKNOWN)


def test_dimension_key_is_not_sealed() -> None:
    """(§2.2) DimensionKey is a plain closed membership token — truthiness is fine (not a verdict)."""
    assert bool(DimensionKey.CONTEXT) is True  # a membership token, never a gate result


def test_denial_values_would_have_failed_open_under_bare_truthiness() -> None:
    """(the trap itself) The denial .value strings are non-empty (would be truthy)."""
    assert bool(str(ProofResult.RESTRICTED.value)) is True
    assert bool(str(ProofResult.UNKNOWN.value)) is True
    assert bool(str(CurrentnessAdmission.DENY.value)) is True


def _bare_truthiness_offenders(path: Path) -> list[str]:
    """Return ``if <name>:`` / ``if not <name>:`` uses of a verdict-shaped local (AST)."""
    suspicious = {"admission", "result", "verdict", "proof_result", "latch"}
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


def test_no_cur_source_uses_bare_truthiness_on_a_verdict() -> None:
    """(source seal) No cur module tests a verdict-shaped value for bare truthiness."""
    sources = sorted(_CUR_SRC.rglob("*.py"))
    assert sources, f"no tos.cur source files found under {_CUR_SRC}"
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
