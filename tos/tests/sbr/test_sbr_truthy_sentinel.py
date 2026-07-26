"""Truthy-sentinel structural seal — __bool__ raises + is-gate regression (design #17 §4.7/§7).

The four decision enums (``ReadinessVerdict`` / ``SessionState`` / ``RecoveryBarrierState`` /
``ObligationResult``) are non-empty ``StrEnum`` strings, so ``if verdict:`` / ``bool(verdict)``
would read a denial member as truthy — a catastrophic silent fail-open (the #14 M1 lesson,
adopted from the start). Each subclasses ``_NonTruthyStrEnum`` (``__bool__`` raises), so the
misuse surfaces as a runtime error. Barrier state is especially critical (§9 line 257 "No
barrier state alone permits").

Regime tag: predicate / model substrate only; SBR-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.sbr import (
    ObligationResult,
    ReadinessVerdict,
    RecoveryBarrierState,
    SessionState,
)

_SBR_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "sbr"

_SEALED_ENUMS = (
    ReadinessVerdict,
    SessionState,
    RecoveryBarrierState,
    ObligationResult,
)


def test_every_sealed_enum_member_raises_on_bool() -> None:
    """(§4.7 structural seal) bool(member) raises TypeError for EVERY member of each sealed enum."""
    for enum in _SEALED_ENUMS:
        for member in enum:
            with pytest.raises(TypeError):
                bool(member)
            with pytest.raises(TypeError):
                # a bare `if member:` also raises (the fail-open path is closed).
                if member:  # pragma: no cover - the branch never executes
                    pass


def test_barrier_state_cannot_be_read_as_permission() -> None:
    """(§9 line 257) No CLOSED_* barrier is truthy-testable — none can read as permission."""
    for member in RecoveryBarrierState:
        with pytest.raises(TypeError):
            bool(member)


def test_is_identity_gate_still_works() -> None:
    """(the mandated gate) Explicit `is` identity comparison is unaffected by the seal."""
    assert (ReadinessVerdict.READY is ReadinessVerdict.READY) is True
    assert (ReadinessVerdict.NOT_READY is ReadinessVerdict.READY) is False
    assert (ObligationResult.SATISFIED is ObligationResult.SATISFIED) is True
    # …and set membership / .value / hashing (none call __bool__).
    assert ReadinessVerdict.NOT_READY in {ReadinessVerdict.NOT_READY}
    assert ReadinessVerdict.READY.value == "READY"
    assert hash(SessionState.ABORTED) == hash(SessionState.ABORTED)


def test_not_ready_would_have_failed_open_under_bare_truthiness() -> None:
    """(the trap itself) NOT_READY / FAILED / a CLOSED_* barrier are non-empty strings (would be truthy)."""
    # The .value strings are non-empty — a plain str truthiness WOULD pass (the fail-open the seal blocks).
    assert bool(str(ReadinessVerdict.NOT_READY.value)) is True
    assert bool(str(ObligationResult.FAILED.value)) is True
    assert bool(str(RecoveryBarrierState.CLOSED_HALTED.value)) is True


def _bare_truthiness_offenders(path: Path) -> list[str]:
    """Return ``if <name>:`` / ``if not <name>:`` uses of a verdict-shaped local (AST)."""
    suspicious = {"verdict", "result", "barrier", "state", "session_state"}
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


def test_no_sbr_source_uses_bare_truthiness_on_a_verdict() -> None:
    """(source seal) No sbr module tests a verdict-shaped value for bare truthiness."""
    sources = sorted(_SBR_SRC.rglob("*.py"))
    assert sources, f"no tos.sbr source files found under {_SBR_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_bare_truthiness_offenders(path))
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"


def test_bare_truthiness_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The AST scan actually catches a planted ``if verdict:`` (not vacuous)."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(verdict):\n    if verdict:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    assert _bare_truthiness_offenders(planted) != []
