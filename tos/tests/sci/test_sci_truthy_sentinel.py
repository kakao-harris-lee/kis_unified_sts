"""Truthy-sentinel seal — every tri-state member is truthy-untestable (design #29 §0.5-3/§2.2).

The ARE #13 / IOC #14 lesson: a non-empty ``StrEnum`` member is truthy, so ``if result:`` would read
a ``DENY`` / ``UNKNOWN`` / ``COMMON_MODE`` as a *go*. Both sci enums raise ``TypeError`` from
``__bool__`` on **every** member (per-member, not just the happy one), and the source contains no
bare truthiness test of a result.

Regime tag: release-admission predicate/model substrate only; closes no SCI-EV; +Security 12/12.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import tos.sci as sci

_SCI_SRC = Path(__file__).resolve().parents[2] / "src" / "tos" / "sci"

_ALL_MEMBERS = [*list(sci.AdmissionResult), *list(sci.IndependenceResult)]


@pytest.mark.parametrize(
    "member", _ALL_MEMBERS, ids=lambda m: f"{type(m).__name__}.{m.name}"
)
def test_bool_raises_type_error_for_every_member(member: object) -> None:
    """(§2.2) ``bool(member)`` raises for every member of both tri-states."""
    with pytest.raises(TypeError, match="not truthy-testable"):
        bool(member)


@pytest.mark.parametrize(
    "member", _ALL_MEMBERS, ids=lambda m: f"{type(m).__name__}.{m.name}"
)
def test_if_member_raises_for_every_member(member: object) -> None:
    """(§2.2) A bare ``if member:`` — the actual fail-open shape — raises loudly."""
    with pytest.raises(TypeError):
        if member:  # noqa: SIM103 — the misuse under test
            pass


@pytest.mark.parametrize(
    "member", _ALL_MEMBERS, ids=lambda m: f"{type(m).__name__}.{m.name}"
)
def test_identity_value_and_hashing_still_work(member: object) -> None:
    """(§2.2) The seal touches only ``__bool__``: identity, value, and hashing are unaffected."""
    assert member is type(member)[member.name]  # type: ignore[index]
    assert isinstance(member.value, str)  # type: ignore[attr-defined]
    assert member in {member}


def test_not_member_also_raises() -> None:
    """(§2.2) ``not result`` routes through ``__bool__`` too — no silent inversion."""
    with pytest.raises(TypeError):
        assert not sci.AdmissionResult.DENY


def _truth_tested_name(node: ast.expr) -> str | None:
    """The result-ish identifier a node truth-tests directly, if any."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _truth_tested_name(node.operand)
    return None


def _truth_tested_operands(node: ast.expr) -> list[ast.expr]:
    """Every sub-expression a node evaluates for truthiness, including ``and`` / ``or`` operands.

    A bare ``if result:`` is only the most visible shape. ``if resolved and result:`` and
    ``x = result or fallback`` evaluate the operand for truthiness just as directly, so the scan
    descends into :class:`ast.BoolOp` operands (recursively, since they nest) rather than looking
    only at the top-level test expression.

    This is a **best-effort static** layer, deliberately not the primary defence: the primary
    defence is structural — :meth:`tos.sci.vocabulary._NonTruthyStrEnum.__bool__` raises
    ``TypeError``, so any truthiness read of a tri-state member fails loudly at runtime whatever
    shape it takes (a call return value, a comprehension condition, an ``assert``). This scan
    catches the readable shapes early; the enum seal is the backstop that has no blind spot.
    """
    if isinstance(node, ast.BoolOp):
        operands: list[ast.expr] = []
        for value in node.values:
            operands.extend(_truth_tested_operands(value))
        return operands
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _truth_tested_operands(node.operand)
    return [node]


def _bare_truth_tests_of_result_names(path: Path) -> list[str]:
    """Return ``if <result-ish name>:`` offenders in one source file (AST)."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        tests: list[ast.expr] = []
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            tests = _truth_tested_operands(node.test)
        elif isinstance(node, ast.BoolOp):
            tests = _truth_tested_operands(node)
        elif isinstance(node, ast.Assert):
            tests = _truth_tested_operands(node.test)
        for test in tests:
            name = _truth_tested_name(test)
            if name and ("result" in name or "verdict" in name):
                offenders.append(f"{path.name}:{node.lineno} bare truth test of {name}")
    return offenders


def test_source_never_truth_tests_a_result() -> None:
    """(§2.2) No sci source reads a tri-state result with a bare truthiness test."""
    offenders: list[str] = []
    for path in sorted(_SCI_SRC.rglob("*.py")):
        offenders.extend(_bare_truth_tests_of_result_names(path))
    assert offenders == [], f"bare truthiness test of a result found: {offenders}"


def test_truth_test_scanner_detects_a_planted_offender(tmp_path: Path) -> None:
    """(both-ways) The scanner catches the bare, negated, and ``and`` / ``or`` operand shapes."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(result, resolved, verdict, fallback):\n"
        "    if result:\n"
        "        return 1\n"
        "    if resolved and verdict:\n"
        "        return 2\n"
        "    if not result:\n"
        "        return 3\n"
        "    chosen = verdict or fallback\n"
        "    while result:\n"
        "        break\n"
        "    return chosen\n",
        encoding="utf-8",
    )
    offenders = " ".join(_bare_truth_tests_of_result_names(planted))
    assert "bare truth test of result" in offenders
    assert "bare truth test of verdict" in offenders
    # the BoolOp operand shapes (`and` / `or`) are caught, not only the top-level test
    assert offenders.count("verdict") >= 2


def test_truth_test_scanner_ignores_explicit_identity_comparisons(
    tmp_path: Path,
) -> None:
    """(both-ways) The mandated ``result is ENUM.MEMBER`` shape is **not** reported."""
    clean = tmp_path / "clean.py"
    clean.write_text(
        "def f(result, resolved):\n"
        "    if result is AdmissionResult.ADMIT and resolved is True:\n"
        "        return 1\n"
        "    return 0\n",
        encoding="utf-8",
    )
    assert _bare_truth_tests_of_result_names(clean) == []
