"""Truthy-sentinel structural seal — __bool__ raises + is-gate regression (design #19 §4.7/§7).

``OrderAdmissibilityResult`` (4-value) and ``TradabilityState`` are non-empty ``StrEnum``
strings, so ``if result:`` / ``bool(result)`` would read a denial member as truthy — a
catastrophic silent fail-open (the #14 M1 lesson, adopted from the start). The single largest
risk this seal blocks is ``RESTRICTED_PROTECTIVE_ONLY`` reading as full permission (§0.4d). Each
subclasses ``_NonTruthyStrEnum`` (``__bool__`` raises), so the misuse surfaces as a runtime
error. ``SessionPhase`` is NOT an enum — it is an injected token judged by membership, never
truthiness (§2.2(3)).

Regime tag: predicate / model substrate only; VTG-EV substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.venue import OrderAdmissibilityResult, TradabilityState

_VENUE_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "venue"

_SEALED_ENUMS = (OrderAdmissibilityResult, TradabilityState)


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


def test_restricted_protective_only_cannot_be_read_as_permission() -> None:
    """(§0.4d — the catastrophic case) RESTRICTED_PROTECTIVE_ONLY is not truthy-testable."""
    with pytest.raises(TypeError):
        bool(OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY)
    with pytest.raises(TypeError):
        if OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY:  # pragma: no cover
            pass


def test_every_admissibility_value_including_restricted_raises() -> None:
    """(§4.7, all four) INADMISSIBLE / UNKNOWN / RESTRICTED_PROTECTIVE_ONLY / ADMISSIBLE all raise on bool."""
    for member in OrderAdmissibilityResult:
        with pytest.raises(TypeError):
            bool(member)


def test_is_identity_gate_still_works() -> None:
    """(the mandated gate) Explicit `is` identity comparison is unaffected by the seal."""
    assert (
        OrderAdmissibilityResult.ADMISSIBLE is OrderAdmissibilityResult.ADMISSIBLE
    ) is True
    assert (
        OrderAdmissibilityResult.INADMISSIBLE is OrderAdmissibilityResult.ADMISSIBLE
    ) is False
    assert (TradabilityState.TRADABLE is TradabilityState.TRADABLE) is True
    # …and set membership / .value / hashing (none call __bool__).
    assert OrderAdmissibilityResult.UNKNOWN in {OrderAdmissibilityResult.UNKNOWN}
    assert OrderAdmissibilityResult.ADMISSIBLE.value == "ADMISSIBLE"
    assert hash(TradabilityState.NOT_TRADABLE) == hash(TradabilityState.NOT_TRADABLE)


def test_denial_values_would_have_failed_open_under_bare_truthiness() -> None:
    """(the trap itself) The denial + protective-only .value strings are non-empty (would be truthy)."""
    assert bool(str(OrderAdmissibilityResult.INADMISSIBLE.value)) is True
    assert bool(str(OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY.value)) is True
    assert bool(str(TradabilityState.NOT_TRADABLE.value)) is True


def _bare_truthiness_offenders(path: Path) -> list[str]:
    """Return ``if <name>:`` / ``if not <name>:`` uses of a result-shaped local (AST)."""
    suspicious = {"result", "admissibility", "tradability", "state", "verdict"}
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


def test_no_venue_source_uses_bare_truthiness_on_a_result() -> None:
    """(source seal) No venue module tests a result-shaped value for bare truthiness."""
    sources = sorted(_VENUE_SRC.rglob("*.py"))
    assert sources, f"no tos.venue source files found under {_VENUE_SRC}"
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
