"""Truthy-sentinel structural seal — the six SIR enums are not truthy-testable (design #28 §4.2).

Every SIR enum member is a non-empty ``StrEnum`` string, so a bare ``if result:`` / ``bool(state)``
would read ``DENY`` / ``HOLD`` / ``SUSPECTED`` / ``CONTAINING`` / ``STABILIZED_NON_LIVE`` /
``UNESTABLISHED_SCOPE_SEVERITY`` as **truthy** — a catastrophic silent fail-open that reads a rejection
or a restrictive state as a go. ``_NonTruthyStrEnum.__bool__`` raises ``TypeError`` on every member (the
#14 M1 ``ConformanceResult.__bool__`` structural-seal precedent), and the consume gates are explicit
positive-identity comparisons.

This file asserts the seal on **all six** enums, member by member, plus the source-level absence of a
truthiness read of a sentinel-bearing value.

Regime tag: predicate substrate only; closes **no** SIR-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import tos.sir as s

_SIR_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "sir"

#: The six enums design #28 §4.2 requires to be truthy-untestable.
_SEALED_ENUMS = (
    s.IncidentLifecycleState,
    s.ClosureDecisionResult,
    s.IncidentRecordState,
    s.CommunicationAssertionKind,
    s.SignalClassificationClass,
    s.ClosureDimension,
)


@pytest.mark.parametrize("enum_type", _SEALED_ENUMS, ids=lambda e: e.__name__)
def test_every_member_raises_on_truthiness(enum_type: type) -> None:
    """(§4.2) ``bool(member)`` raises ``TypeError`` for every member of every sealed enum."""
    members = list(enum_type)
    assert members, f"{enum_type.__name__} has no members"
    for member in members:
        with pytest.raises(TypeError):
            bool(member)


@pytest.mark.parametrize("enum_type", _SEALED_ENUMS, ids=lambda e: e.__name__)
def test_identity_value_and_membership_still_work(enum_type: type) -> None:
    """(§4.2) The seal touches only ``__bool__`` — identity, value, hashing and membership are intact."""
    for member in enum_type:
        assert member is enum_type(member.value)
        assert isinstance(member.value, str)
        assert member in frozenset(enum_type)
        assert {member: 1}[member] == 1


def test_denial_members_are_non_empty_strings() -> None:
    """(§4.2 rationale) The denial / restrictive members are exactly the truthy strings the seal blocks."""
    for member in (
        s.ClosureDecisionResult.DENY,
        s.ClosureDecisionResult.HOLD,
        s.IncidentLifecycleState.SUSPECTED,
        s.IncidentLifecycleState.CONTAINING,
        s.IncidentLifecycleState.STABILIZED_NON_LIVE,
        s.SignalClassificationClass.UNESTABLISHED_SCOPE_SEVERITY,
    ):
        assert member.value != ""


def test_closure_consume_gate_is_positive_identity() -> None:
    """(§4.2) The closure gate admits **only** ``CLOSE_ADMINISTRATIVELY`` — DENY / HOLD are non-closure."""
    from ._sir_strategies import clean_closure_decision

    assert s.closure_administrative_non_permissive(clean_closure_decision()) is True
    for denial in (s.ClosureDecisionResult.DENY, s.ClosureDecisionResult.HOLD):
        # a DENY / HOLD decision skips the §20 coexistence seal, so it is constructible ...
        decision = clean_closure_decision(result=denial)
        # ... and is never read as a closure.
        assert s.closure_administrative_non_permissive(decision) is False


def test_absent_result_denies() -> None:
    """(§4.2 / ∅-seal) A decision with no result at all is never a closure."""
    from ._sir_strategies import clean_closure_decision

    assert (
        s.closure_administrative_non_permissive(clean_closure_decision(result=None))
        is False
    )


#: Identifiers that may hold a truthy-untestable sentinel — reading any of them in a boolean context
#: would be the §4.2 fail-open (a ``DENY`` / ``SUSPECTED`` string read as a go).
_SENTINEL_BEARING_NAMES = frozenset(
    {
        "result",
        "state",
        "lifecycle_state",
        "record_state",
        "classification",
        "assertion_kind",
        "claimed_as",
        "step_kind",
        "dimension",
        "member_state",
    }
)


def _boolean_context_names(tree: ast.AST) -> list[tuple[int, str]]:
    """Every identifier read in a boolean context (``if`` / ``while`` / ``not`` / ``and`` / ``or``)."""
    found: list[tuple[int, str]] = []

    def record(node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            found.append((node.lineno, node.id))
        elif isinstance(node, ast.Attribute):
            found.append((node.lineno, node.attr))

    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            record(node.test)
        elif isinstance(node, ast.BoolOp):
            for value in node.values:
                record(value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            record(node.operand)
        elif isinstance(node, ast.comprehension):
            for condition in node.ifs:
                record(condition)
    return found


def test_no_sir_source_reads_a_sentinel_value_for_truthiness() -> None:
    """(§4.2 source scan) No sir source reads a sentinel-bearing name in a boolean context.

    An AST scan, not a text scan: the seal is about *code*, and a docstring that quotes the forbidden
    ``if result:`` pattern to explain the seal must not be mistaken for the offence.
    """
    offenders: list[str] = []
    for path in sorted(_SIR_SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, name in _boolean_context_names(tree):
            if name in _SENTINEL_BEARING_NAMES:
                offenders.append(f"{path.name}:{lineno} boolean read of {name!r}")
    assert offenders == [], f"truthiness read of a sentinel-bearing value: {offenders}"


def test_truthy_scan_detects_a_planted_offender(tmp_path: Path) -> None:
    """(canary) The AST scan catches a planted ``if result:`` / ``if not state:`` — not vacuous."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        '"""A docstring mentioning `if result:` must NOT count as an offence."""\n'
        "def f(result, obj):\n"
        "    if result:\n"
        "        return 1\n"
        "    if not obj.state:\n"
        "        return 2\n"
        "    return 0\n",
        encoding="utf-8",
    )
    tree = ast.parse(planted.read_text(encoding="utf-8"), filename="planted")
    names = {name for _, name in _boolean_context_names(tree)}
    assert "result" in names
    assert "state" in names


def test_every_sealed_enum_subclasses_the_local_non_truthy_base() -> None:
    """(§3.3) The seal is authored **locally** in ``tos.sir.vocabulary`` — no sibling import."""
    bases = {
        base.__name__
        for enum_type in _SEALED_ENUMS
        for base in enum_type.__mro__
        if base.__name__.startswith("_NonTruthy")
    }
    assert bases == {"_NonTruthyStrEnum"}
    tree = ast.parse(
        (_SIR_SRC / "vocabulary.py").read_text(encoding="utf-8"), filename="vocabulary"
    )
    defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert "_NonTruthyStrEnum" in defined, (
        "_NonTruthyStrEnum must be authored locally-fresh in tos.sir.vocabulary "
        "(sibling edge 0 — design #28 §3.3)"
    )
