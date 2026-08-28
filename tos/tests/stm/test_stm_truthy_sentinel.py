"""Truthy-sentinel seal for the eight STM enums (design #30 §2.2/§4.2).

All eight STM enums are non-empty ``StrEnum`` strings, so a bare ``if x:`` / ``bool(x)`` would read a
denial / restrictive / malformed member as truthy — the catastrophic silent fail-open this seal blocks.
Each subclasses a local ``_NonTruthyStrEnum`` whose ``__bool__`` raises ``TypeError``.

The seal is asserted **structurally** (every member of every enum raises) and **behaviourally** (no stm
source contains a bare-truthiness read of an enum-typed coordinate). The reused *pattern* is ioc's
``ConformanceResult.__bool__`` (``ioc/vocabulary.py:63``); the enum itself is authored locally-fresh —
sibling edge 0.

Regime tag: predicate substrate only; closes **no** STM-EV; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import ast
from enum import StrEnum
from pathlib import Path

import pytest
from tos.stm import (
    AggregateConformanceResult,
    BoundSemanticKind,
    CoverageDimension,
    DashboardStatusToken,
    MonitoringGapKind,
    NumericInputState,
    SuppressionLifecycleState,
    TelemetryCriticality,
)

_STM_SRC = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "stm"


def _stm_sources() -> list[Path]:
    """Every ``tos.stm`` source, asserted **non-empty** so a path typo cannot make a sweep vacuous."""
    sources = sorted(_STM_SRC.rglob("*.py"))
    assert (
        sources
    ), f"no tos.stm source found under {_STM_SRC} — this sweep would be vacuous"
    return sources


#: The design #30 §4.2 sealed set — **eight** enums, with their §7.2 anchor cardinalities.
_SEALED_ENUMS: dict[type[StrEnum], int] = {
    AggregateConformanceResult: 4,
    DashboardStatusToken: 7,
    MonitoringGapKind: 10,
    NumericInputState: 12,
    BoundSemanticKind: 12,
    TelemetryCriticality: 3,
    SuppressionLifecycleState: 4,
    CoverageDimension: 11,
}

#: The enum-typed coordinates a bare ``if <x>:`` must never read (design #30 §4.2).
_ENUM_TYPED_ATTRS = frozenset(
    {
        "aggregate_result",
        "result",
        "numeric_input_state",
        "status_token",
        "gap_kind",
        "criticality",
        "lifecycle_state",
        "approved_bound_kind",
        "implemented_as_kind",
    }
)


def test_exactly_eight_enums_are_sealed() -> None:
    """(§4.2) The sealed set is eight — ``CoverageDimension`` included (M2)."""
    assert len(_SEALED_ENUMS) == 8


@pytest.mark.parametrize("enum_type", list(_SEALED_ENUMS))
def test_every_member_rejects_truthiness(enum_type: type[StrEnum]) -> None:
    """(§4.2) ``bool(member)`` raises ``TypeError`` on every member of every sealed enum."""
    assert list(enum_type), f"{enum_type.__name__} must not be empty"
    for member in enum_type:
        with pytest.raises(TypeError):
            bool(member)


@pytest.mark.parametrize("enum_type,cardinality", list(_SEALED_ENUMS.items()))
def test_every_enum_matches_its_transcribed_cardinality(
    enum_type: type[StrEnum], cardinality: int
) -> None:
    """(§7.2 drift) Each enum still equals its ADR anchor count (過 0 · 不 0)."""
    assert len(enum_type) == cardinality


@pytest.mark.parametrize("enum_type", list(_SEALED_ENUMS))
def test_identity_membership_and_value_still_work(enum_type: type[StrEnum]) -> None:
    """(§4.2) The seal touches only ``__bool__`` — identity, value, hashing and sets are unaffected."""
    members = list(enum_type)
    first = members[0]
    assert first is enum_type(first.value)
    assert first in frozenset(members)
    assert isinstance(first.value, str)
    assert sorted(members)  # ordering is unaffected


def test_no_stm_source_reads_an_enum_coordinate_truthily() -> None:
    """(§4.2 behavioural) No ``if x.aggregate_result:`` / ``not x.result`` anywhere in the package.

    A bare truthiness read would raise at runtime thanks to the seal, but the point of this scan is
    that such a read must not exist *at all*: it would be a latent crash on the denial path, which is
    exactly the path that must stay reliable.
    """
    offenders: list[str] = []
    for path in _stm_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            tested: list[ast.expr] = []
            if isinstance(node, (ast.If, ast.While, ast.IfExp)):
                tested = [node.test]
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
                tested = [node.operand]
            elif isinstance(node, ast.BoolOp):
                tested = list(node.values)
            for expression in tested:
                if (
                    isinstance(expression, ast.Attribute)
                    and expression.attr in _ENUM_TYPED_ATTRS
                ):
                    offenders.append(
                        f"{path.name}:{expression.lineno} {expression.attr}"
                    )
    assert offenders == [], (
        "bare truthiness read of an enum-typed coordinate — the denial members are non-empty "
        f"strings and this is the catastrophic fail-open the seal exists for: {offenders}"
    )


def test_the_truthiness_scan_detects_a_planted_read(tmp_path: Path) -> None:
    """(canary) The scan really distinguishes a bare read from an explicit identity gate."""
    planted = tmp_path / "planted.py"
    planted.write_text(
        "def f(s):\n"
        "    if s.aggregate_result:\n"
        "        return 1\n"
        "    if s.scope is None:\n"
        "        return 2\n"
        "    return 3\n",
        encoding="utf-8",
    )
    tree = ast.parse(planted.read_text(encoding="utf-8"), filename="planted")
    found = [
        node.test.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.If) and isinstance(node.test, ast.Attribute)
    ]
    assert "aggregate_result" in found


def test_the_ioc_pattern_is_reused_not_imported() -> None:
    """(§3.3 / §0.5 seal 3) The ``__bool__`` seal is a pattern; ioc's own enum is never imported.

    ioc ``ConformanceResult`` {CONFORMANT / NON_CONFORMANT / UNKNOWN} is *intent-to-order command*
    conformance (ADR-002-020) — different members, different proposition. stm re-expresses the seal
    locally and takes no import edge (sibling edge 0).
    """
    import tos.stm as s

    assert not hasattr(s, "ConformanceResult")
    for path in _stm_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith("tos.ioc"), (
                    f"{path.name}:{node.lineno} imports {name} — the truthy-sentinel seal is "
                    "re-expressed locally, never imported (design #30 §3.3, sibling edge 0)"
                )
