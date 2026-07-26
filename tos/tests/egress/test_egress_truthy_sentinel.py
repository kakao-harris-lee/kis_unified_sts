"""Truthy-sentinel structural seal — __bool__ raises + is-gate regression (design #22 §2.2/§4.7/§7).

``EgressAdmission`` (ADMIT / DENY), ``CommitProofValidity`` (VALID / INVALID / UNKNOWN), and
``RestrictiveLatchState`` (CLEAR / DENY_LATCHED) are non-empty ``StrEnum`` strings, so ``if
admission:`` / ``bool(validity)`` / ``if state:`` would read a **denial** member as truthy — a
catastrophic silent fail-open that reads a *rejection* (DENY / INVALID / UNKNOWN / DENY_LATCHED) as
an *admission* (the #13/#14 M1 lesson, adopted from the start). Each subclasses ``_NonTruthyStrEnum``
(``__bool__`` raises), so the misuse surfaces as a runtime error. ``SignerRole`` is a plain closed
StrEnum (membership token), deliberately NOT sealed.

Regime tag: structural / coordinate predicate substrate only; EGRESS vocabulary substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.egress import CommitProofValidity, EgressAdmission, RestrictiveLatchState

_EGRESS_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "egress"

_SEALED_ENUMS = (EgressAdmission, CommitProofValidity, RestrictiveLatchState)


def test_every_sealed_enum_member_raises_on_bool() -> None:
    """(§4.7 structural seal) bool(member) raises TypeError for EVERY member of each sealed enum."""
    for enum in _SEALED_ENUMS:
        for member in enum:
            with pytest.raises(TypeError):
                bool(member)
            with pytest.raises(TypeError):
                if member:  # pragma: no cover - the branch never executes
                    pass


def test_deny_members_cannot_be_read_as_admission() -> None:
    """(§4.7 — the catastrophic case) DENY / INVALID / UNKNOWN / DENY_LATCHED are not truthy."""
    for member in (
        EgressAdmission.DENY,
        CommitProofValidity.INVALID,
        CommitProofValidity.UNKNOWN,
        RestrictiveLatchState.DENY_LATCHED,
    ):
        with pytest.raises(TypeError):
            bool(member)


def test_is_identity_gate_still_works() -> None:
    """(the mandated gate) Explicit `is` identity comparison is unaffected by the seal."""
    assert (EgressAdmission.ADMIT is EgressAdmission.ADMIT) is True
    assert (EgressAdmission.DENY is EgressAdmission.ADMIT) is False
    assert (CommitProofValidity.VALID is CommitProofValidity.VALID) is True
    assert (RestrictiveLatchState.CLEAR is RestrictiveLatchState.CLEAR) is True
    # …and set membership / .value / hashing (none call __bool__).
    assert EgressAdmission.ADMIT in {EgressAdmission.ADMIT}
    assert CommitProofValidity.VALID.value == "VALID"
    assert hash(RestrictiveLatchState.DENY_LATCHED) == hash(
        RestrictiveLatchState.DENY_LATCHED
    )


def test_denial_values_would_have_failed_open_under_bare_truthiness() -> None:
    """(the trap itself) The denial .value strings are non-empty (would be truthy)."""
    assert bool(str(EgressAdmission.DENY.value)) is True
    assert bool(str(CommitProofValidity.UNKNOWN.value)) is True
    assert bool(str(RestrictiveLatchState.DENY_LATCHED.value)) is True


def _bare_truthiness_offenders(path: Path) -> list[str]:
    """Return ``if <name>:`` / ``if not <name>:`` uses of a verdict-shaped local (AST)."""
    suspicious = {"admission", "validity", "state", "latch_state", "verdict", "result"}
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


def test_no_egress_source_uses_bare_truthiness_on_a_verdict() -> None:
    """(source seal) No egress module tests a verdict-shaped value for bare truthiness."""
    sources = sorted(_EGRESS_SRC.rglob("*.py"))
    assert sources, f"no tos.egress source files found under {_EGRESS_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_bare_truthiness_offenders(path))
    assert offenders == [], f"truthy-sentinel trap reachable: {offenders}"


def test_bare_truthiness_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The AST scan actually catches a planted ``if state:`` (not vacuous)."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(state):\n    if state:\n        return 1\n    return 0\n",
        encoding="utf-8",
    )
    assert _bare_truthiness_offenders(planted) != []
