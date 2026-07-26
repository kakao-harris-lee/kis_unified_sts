"""Truthy-sentinel structural seal — __bool__ raises + is-gate regression (design #20 §2.2/§4.7/§7).

``AttestationDecision`` (APPROVE / DENY / ABSTAIN) and ``ApprovalLifecycleState`` are non-empty
``StrEnum`` strings, so ``if decision:`` / ``bool(state)`` would read a **denial** (``DENY`` /
``ABSTAIN``) or **terminal** (``EXPIRED`` / ``REVOKED`` / ...) member as truthy — a catastrophic
silent fail-open that reads a *rejection* as an *approval* (the #13/#14 M1 lesson, adopted from the
start). Each subclasses ``_NonTruthyStrEnum`` (``__bool__`` raises), so the misuse surfaces as a
runtime error. ``AuthorityClass`` / ``ConflictRole`` are plain closed StrEnums (membership tokens),
deliberately NOT sealed.

Regime tag: predicate / model substrate only; HAG vocabulary substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.hag import ApprovalLifecycleState, AttestationDecision

_HAG_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "hag"

_SEALED_ENUMS = (AttestationDecision, ApprovalLifecycleState)


def test_every_sealed_enum_member_raises_on_bool() -> None:
    """(§4.7 structural seal) bool(member) raises TypeError for EVERY member of each sealed enum."""
    for enum in _SEALED_ENUMS:
        for member in enum:
            with pytest.raises(TypeError):
                bool(member)
            with pytest.raises(TypeError):
                if member:  # pragma: no cover - the branch never executes
                    pass


def test_deny_and_abstain_cannot_be_read_as_approval() -> None:
    """(§4.7 — the catastrophic case) DENY / ABSTAIN are not truthy-testable (would read as approve)."""
    for member in (AttestationDecision.DENY, AttestationDecision.ABSTAIN):
        with pytest.raises(TypeError):
            bool(member)


def test_terminal_lifecycle_states_cannot_be_read_as_live() -> None:
    """(§4.7) EXPIRED / REVOKED / DENIED / INVALIDATED / SUPERSEDED / CONSUMED all raise on bool."""
    for member in (
        ApprovalLifecycleState.EXPIRED,
        ApprovalLifecycleState.REVOKED,
        ApprovalLifecycleState.DENIED,
        ApprovalLifecycleState.INVALIDATED,
        ApprovalLifecycleState.SUPERSEDED,
        ApprovalLifecycleState.CONSUMED,
    ):
        with pytest.raises(TypeError):
            bool(member)


def test_is_identity_gate_still_works() -> None:
    """(the mandated gate) Explicit `is` identity comparison is unaffected by the seal."""
    assert (AttestationDecision.APPROVE is AttestationDecision.APPROVE) is True
    assert (AttestationDecision.DENY is AttestationDecision.APPROVE) is False
    assert (
        ApprovalLifecycleState.QUORUM_SATISFIED
        is ApprovalLifecycleState.QUORUM_SATISFIED
    ) is True
    # …and set membership / .value / hashing (none call __bool__).
    assert AttestationDecision.APPROVE in {AttestationDecision.APPROVE}
    assert AttestationDecision.APPROVE.value == "APPROVE"
    assert hash(ApprovalLifecycleState.EXPIRED) == hash(ApprovalLifecycleState.EXPIRED)


def test_denial_values_would_have_failed_open_under_bare_truthiness() -> None:
    """(the trap itself) The denial / terminal .value strings are non-empty (would be truthy)."""
    assert bool(str(AttestationDecision.DENY.value)) is True
    assert bool(str(ApprovalLifecycleState.EXPIRED.value)) is True


def _bare_truthiness_offenders(path: Path) -> list[str]:
    """Return ``if <name>:`` / ``if not <name>:`` uses of a decision-shaped local (AST)."""
    suspicious = {"decision", "state", "result", "lifecycle_state", "verdict"}
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


def test_no_hag_source_uses_bare_truthiness_on_a_decision() -> None:
    """(source seal) No hag module tests a decision-shaped value for bare truthiness."""
    sources = sorted(_HAG_SRC.rglob("*.py"))
    assert sources, f"no tos.hag source files found under {_HAG_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_bare_truthiness_offenders(path))
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"


def test_bare_truthiness_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The AST scan actually catches a planted ``if decision:`` (not vacuous)."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(decision):\n    if decision:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    assert _bare_truthiness_offenders(planted) != []
