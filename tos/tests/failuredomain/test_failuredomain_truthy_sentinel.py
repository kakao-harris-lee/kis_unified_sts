"""Truthy / falsy forgery seal + ``is``-identity discipline (design #27 §4 / §2.1A m5).

The four failuredomain vocabularies are **plain, closed** ``StrEnum``s (the rlp ``ScopeDimension``
precedent, design #27 §2.1A m5) — deliberately **not** truthy-sealed, because they are consumed by
``is`` identity and set membership, never as a gate result. That choice has a cost: every member is
truthy, so a bare ``if status:`` would silently read ``COMMON_MODE`` / ``UNKNOWN`` as "go". This
file pays that cost explicitly.

Three seals:

  1. **Structural** — an AST scan proves no ``tos.failuredomain`` source ever uses a bare name or
     attribute as a condition (the ``if status:`` idiom simply does not occur), and a planted-source
     canary proves the scan detects one;
  2. **Identity** — the FD vocabularies are never compared with ``==`` in package code; ``==`` is
     reserved for injected sibling tokens (bare strings), ``is`` for this package's own members
     (design #27 §3.2);
  3. **Behavioural** — falsy inputs (``""``, ``None``, bare ``frozenset()``) and **truthy blanks**
     (``" "``, ``"\\t"``) are exercised against every predicate and never forge a positive verdict.

Regime tag: EV-L1 predicate substrate only; closes no FD-EV; the L1-decidable content is
sibling-owned per design #27 §3.5.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tos.failuredomain import (
    ExplicitlyAnalyzedEmpty,
    FailureBehaviorKind,
    FailureDomainKind,
    IsolationClaimStatus,
    IsolationKind,
    decision_sole_sourced_from_volatile,
    new_risk_blocked_by_unproven_isolation,
    unproven_isolation_is_common_mode,
)

from ._failuredomain_strategies import BLANK_TEXTS, clean_claim

_FD_SRC = (
    Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "failuredomain"
)

#: The package's own vocabularies — compared with ``is``, never ``==`` (design #27 §3.2).
_OWN_VOCABULARIES = frozenset(
    {
        "FailureDomainKind",
        "FailureBehaviorKind",
        "IsolationClaimStatus",
        "IsolationKind",
        "ExplicitlyAnalyzedEmpty",
    }
)


def _condition_leaves(node: ast.expr) -> list[ast.expr]:
    """Flatten a condition expression through ``and`` / ``or`` / ``not`` into its leaves."""
    if isinstance(node, ast.BoolOp):
        leaves: list[ast.expr] = []
        for value in node.values:
            leaves.extend(_condition_leaves(value))
        return leaves
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _condition_leaves(node.operand)
    return [node]


def _truthy_read_offenders(path: Path) -> list[str]:
    """Return conditions that read a bare name / attribute for truthiness (the forbidden idiom)."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        tests: list[ast.expr] = []
        if isinstance(node, (ast.If, ast.IfExp, ast.While)):
            tests.append(node.test)
        elif isinstance(node, ast.BoolOp):
            # an ``and`` / ``or`` chain is a truthiness context WHEREVER it appears — including
            # in a ``return`` or an assignment, which no ``if``-only scan would ever reach.
            tests.extend(node.values)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            tests.append(node.operand)
        elif isinstance(node, ast.Assert):
            tests.append(node.test)
        elif isinstance(node, ast.comprehension):
            tests.extend(node.ifs)
        for test in tests:
            for leaf in _condition_leaves(test):
                if isinstance(leaf, (ast.Name, ast.Attribute, ast.Subscript)):
                    offenders.append(
                        f"{path.name}:{leaf.lineno} bare truthiness read "
                        f"({ast.unparse(leaf)})"
                    )
    return offenders


def _equality_on_own_vocabulary(path: Path) -> list[str]:
    """Return ``==`` / ``!=`` comparisons whose operand is one of this package's own enums."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops):
            continue
        for operand in (node.left, *node.comparators):
            if (
                isinstance(operand, ast.Attribute)
                and isinstance(operand.value, ast.Name)
                and operand.value.id in _OWN_VOCABULARIES
            ):
                offenders.append(
                    f"{path.name}:{node.lineno} == on own vocabulary "
                    f"({ast.unparse(operand)})"
                )
    return offenders


# --- 1. structural: no bare truthiness read ---------------------------------


def test_no_source_reads_a_bare_name_for_truthiness() -> None:
    """(1) No ``if status:`` / ``if claim.assumptions:`` anywhere — every guard is explicit."""
    sources = sorted(_FD_SRC.rglob("*.py"))
    assert sources, f"no tos.failuredomain source found under {_FD_SRC}"
    offenders: list[str] = []
    for path in sources:
        offenders.extend(_truthy_read_offenders(path))
    assert offenders == [], f"bare truthiness reads found: {offenders}"


def test_the_truthy_scan_detects_a_planted_read(tmp_path: Path) -> None:
    """(both-ways) The scan is not neutered — a planted ``if status:`` is caught."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(status, claim):\n"
        "    if status:\n"
        "        return True\n"
        "    if claim.assumptions:\n"
        "        return True\n"
        "    return False\n",
        encoding="utf-8",
    )
    offenders = _truthy_read_offenders(planted)
    joined = " ".join(offenders)
    assert "status" in joined
    assert "claim.assumptions" in joined


def test_the_truthy_scan_detects_reads_outside_an_if(tmp_path: Path) -> None:
    """(both-ways, widened) A truthiness read in a ``return`` / ``assert`` / ``not`` is caught too.

    An ``if``-only scan is trivially evaded: ``return status and x`` reads ``status`` for
    truthiness without ever writing ``if``. The scan therefore treats every ``and`` / ``or``
    chain, every ``not`` operand, every conditional expression, every ``assert`` and every
    comprehension filter as a condition context, wherever it appears.
    """
    planted = tmp_path / "planted_boolop.py"
    planted.write_text(
        "def f(status, claim, rows):\n"
        "    a = status and claim\n"
        "    b = not claim\n"
        "    c = claim if status else None\n"
        "    assert claim\n"
        "    d = [r for r in rows if r]\n"
        "    return status or claim\n",
        encoding="utf-8",
    )
    offenders = _truthy_read_offenders(planted)
    joined = " ".join(offenders)
    for expected in ("status", "claim", "r"):
        assert expected in joined, f"{expected} truthiness read was NOT detected"
    assert len(offenders) >= 6


# --- 2. identity: `is`, never `==`, on this package's own vocabularies -------


def test_no_source_compares_its_own_vocabulary_with_equality() -> None:
    """(2 / §3.2) FD's own enums are matched with ``is``; ``==`` is for injected sibling tokens."""
    offenders: list[str] = []
    for path in sorted(_FD_SRC.rglob("*.py")):
        offenders.extend(_equality_on_own_vocabulary(path))
    assert offenders == [], f"equality comparison on an own vocabulary: {offenders}"


def test_the_equality_scan_detects_a_planted_comparison(tmp_path: Path) -> None:
    """(both-ways) The scan catches a planted ``status == IsolationClaimStatus.ESTABLISHED``."""
    planted = tmp_path / "planted_eq.py"
    planted.write_text(
        "def f(status):\n" "    return status == IsolationClaimStatus.ESTABLISHED\n",
        encoding="utf-8",
    )
    assert _equality_on_own_vocabulary(planted) != []


def test_members_are_truthy_which_is_exactly_why_the_scan_exists() -> None:
    """(2) Documented cost of the plain-StrEnum choice: COMMON_MODE and UNKNOWN are truthy."""
    for enum_type in (
        FailureDomainKind,
        FailureBehaviorKind,
        IsolationClaimStatus,
        IsolationKind,
    ):
        for member in enum_type:
            assert bool(member) is True
    assert bool(IsolationClaimStatus.COMMON_MODE) is True
    assert bool(IsolationClaimStatus.UNKNOWN) is True
    assert bool(ExplicitlyAnalyzedEmpty.EXPLICITLY_ANALYZED_EMPTY) is True


def test_a_string_equal_to_a_member_is_not_the_member() -> None:
    """(2) A raw ``str`` compares equal to a StrEnum member but is not it — hence ``is`` gates."""
    raw = "ESTABLISHED"
    assert raw == IsolationClaimStatus.ESTABLISHED
    assert raw is not IsolationClaimStatus.ESTABLISHED
    # a forged raw string can never unblock, because the gate is identity-based.
    assert new_risk_blocked_by_unproven_isolation("ESTABLISHED") is True  # type: ignore[arg-type]


def test_a_look_alike_status_from_another_axis_never_unblocks() -> None:
    """(2 / §3.3) IsolationKind.COMMON_MODE shares a token with the status axis and never crosses."""
    assert new_risk_blocked_by_unproven_isolation(IsolationKind.COMMON_MODE) is True  # type: ignore[arg-type]
    assert new_risk_blocked_by_unproven_isolation(IsolationKind.PHYSICAL) is True  # type: ignore[arg-type]


# --- 3. behavioural: falsy and truthy-blank forgery --------------------------


@pytest.mark.parametrize("falsy", [None, "", 0, frozenset(), (), False])
def test_no_falsy_input_ever_unblocks_new_risk(falsy: object) -> None:
    """(3) Every falsy value blocks — a falsy sentinel cannot masquerade as ESTABLISHED."""
    assert new_risk_blocked_by_unproven_isolation(falsy) is True  # type: ignore[arg-type]


@pytest.mark.parametrize("blank", BLANK_TEXTS)
def test_truthy_blank_strings_never_establish_a_claim(blank: str) -> None:
    """(3) ``" "`` is truthy yet states nothing — the strip-based gate rejects it."""
    assert unproven_isolation_is_common_mode(clean_claim(residual_risk=blank)) is True
    assert (
        unproven_isolation_is_common_mode(clean_claim(assumptions=frozenset({blank})))
        is True
    )


def test_empty_collections_never_flip_the_volatile_verdict_to_permissive() -> None:
    """(3) The ∅ cases of the volatile predicate stay conservative or explicitly declared."""
    assert decision_sole_sourced_from_volatile(frozenset(), frozenset()) is True
    assert decision_sole_sourced_from_volatile(frozenset(), None) is None
